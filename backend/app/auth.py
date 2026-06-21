"""Al-Wilayat — authentication & account security.

Endpoints (prefix /api/auth):
    POST /register          full_name, email, password   -> token + user
    POST /login             email, password, remember     -> token + user
    GET  /me                (Bearer token)                -> user profile
    POST /forgot-password   email                          -> generic 200
    GET  /reset/validate    token                          -> {valid: bool}
    POST /reset-password    token, password                -> 200 / 400

Security features
    * bcrypt password hashing (passlib) — never plain text
    * server-side password policy (>=8 chars, upper, lower, digit, special)
    * e-mail format validation
    * JWT access tokens (python-jose); longer TTL when "remember me" is set
    * per-IP + per-email login rate limiting / brute-force lockout
    * admin alert e-mail after repeated failures (see email_utils)
    * secure, time-limited password-reset tokens, stored only as a hash
    * generic errors that never reveal whether an e-mail is registered

NOTE: users and reset tokens live in memory for this demo. The boundaries are
DB-ready: swap `_USERS` / `_RESETS` for real tables (e.g. PostgreSQL) and move
the lookups into a repository layer. Secrets come from env (WILAYAT_SECRET).
"""
import hashlib
import os
import re
import secrets
import sqlite3
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel

from app import email_utils

# ---------------------------------------------------------------- config -----
SECRET_KEY = os.getenv("WILAYAT_SECRET", "dev-only-change-me")
ALGORITHM = "HS256"
TOKEN_TTL_MIN = 60 * 12            # normal session: 12 hours
TOKEN_TTL_REMEMBER_MIN = 60 * 24 * 30   # "remember me": 30 days
CODE_TTL_MIN = 15                  # password-reset code validity
CODE_MAX_TRIES = 5                 # wrong-code attempts before the code is voided

# Brute-force protection
MAX_FAILS = 5                      # failures allowed within the window
FAIL_WINDOW_SEC = 15 * 60          # rolling window
LOCK_SEC = 15 * 60                 # lockout duration once tripped

FRONTEND_BASE = os.getenv("FRONTEND_BASE", "http://localhost:5500")

router = APIRouter(prefix="/api/auth", tags=["auth"])
pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2 = OAuth2PasswordBearer(tokenUrl="/api/auth/login", auto_error=False)

# ---- Persistent user store (SQLite) ----------------------------------------
# Accounts survive server restarts, so users only sign up once and can sign in
# any time afterwards. Swap this for PostgreSQL in production if desired.
DB_PATH = Path(os.getenv("WILAYAT_DB", Path(__file__).resolve().parent / "data" / "users.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)


def _db() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _init_db() -> None:
    with _db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS users (
                email     TEXT PRIMARY KEY,
                full_name TEXT NOT NULL,
                hash      TEXT NOT NULL,
                role      TEXT NOT NULL,
                created   TEXT NOT NULL
            )"""
        )


_init_db()


def get_user(email: str) -> dict | None:
    with _db() as conn:
        row = conn.execute("SELECT * FROM users WHERE email = ?", ((email or "").lower(),)).fetchone()
        return dict(row) if row else None


def count_users() -> int:
    with _db() as conn:
        return conn.execute("SELECT COUNT(*) AS n FROM users").fetchone()["n"]


def add_user(email: str, full_name: str, pw_hash: str, role: str) -> dict:
    user = {"email": email, "full_name": full_name, "hash": pw_hash,
            "role": role, "created": _now().isoformat()}
    with _db() as conn:
        conn.execute(
            "INSERT INTO users (email, full_name, hash, role, created) VALUES (?, ?, ?, ?, ?)",
            (user["email"], user["full_name"], user["hash"], user["role"], user["created"]),
        )
    return user


def set_password(email: str, pw_hash: str) -> None:
    with _db() as conn:
        conn.execute("UPDATE users SET hash = ? WHERE email = ?", (pw_hash, (email or "").lower()))


# In-memory stores (fine to lose on restart) ---------------------------------
# _CODES: {email: {"hash", "expires", "tries"}}  — short-lived reset codes
_CODES: dict[str, dict] = {}
# _FAILS: {key: {"count", "first", "locked_until", "alerted"}}
_FAILS: dict[str, dict] = {}

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
GENERIC_LOGIN_ERR = "Incorrect email or password"


# --------------------------------------------------------------- schemas -----
class RegisterIn(BaseModel):
    full_name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str
    remember: bool = False


class ForgotIn(BaseModel):
    email: str


class ResetIn(BaseModel):
    email: str
    code: str
    password: str


class UserOut(BaseModel):
    full_name: str
    email: str
    role: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# --------------------------------------------------------------- helpers -----
def _now() -> datetime:
    return datetime.now(timezone.utc)


def validate_email(email: str) -> str:
    email = (email or "").strip().lower()
    if not EMAIL_RE.match(email):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Enter a valid email address")
    return email


def validate_password(password: str) -> None:
    """Enforce the password policy. Raises 422 with a clear message on failure."""
    problems = []
    if len(password or "") < 8:
        problems.append("at least 8 characters")
    if not re.search(r"[A-Z]", password or ""):
        problems.append("an uppercase letter")
    if not re.search(r"[a-z]", password or ""):
        problems.append("a lowercase letter")
    if not re.search(r"\d", password or ""):
        problems.append("a number")
    if not re.search(r"[^A-Za-z0-9]", password or ""):
        problems.append("a special character")
    if problems:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "Password needs " + ", ".join(problems) + ".")


def _make_token(user: dict, remember: bool = False) -> str:
    ttl = TOKEN_TTL_REMEMBER_MIN if remember else TOKEN_TTL_MIN
    payload = {
        "sub": user["email"],
        "name": user["full_name"],
        "role": user["role"],
        "exp": _now() + timedelta(minutes=ttl),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def _user_out(user: dict) -> UserOut:
    return UserOut(full_name=user["full_name"], email=user["email"], role=user["role"])


def _hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


# ----------------------------------------------------------- rate limiting ---
def _client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.client.host if request.client else ""


def _check_lock(key: str) -> None:
    rec = _FAILS.get(key)
    if rec and rec.get("locked_until", 0) > time.time():
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            "Too many failed attempts. Please wait a few minutes and try again.",
        )


def _record_failure(key: str, attempted_email: str, request: Request) -> None:
    now = time.time()
    rec = _FAILS.get(key)
    if not rec or now - rec["first"] > FAIL_WINDOW_SEC:
        rec = {"count": 0, "first": now, "locked_until": 0, "alerted": False}
    rec["count"] += 1
    if rec["count"] >= MAX_FAILS:
        rec["locked_until"] = now + LOCK_SEC
        if not rec["alerted"]:
            rec["alerted"] = True
            email_utils.send_admin_alert(
                attempted_email=attempted_email,
                ip=_client_ip(request),
                user_agent=request.headers.get("user-agent", ""),
                when=_now().strftime("%Y-%m-%d %H:%M:%S UTC"),
            )
    _FAILS[key] = rec


def _clear_failures(key: str) -> None:
    _FAILS.pop(key, None)


# --------------------------------------------------- current-user dependency -
def current_user(token: str = Depends(oauth2)) -> dict:
    creds_err = HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired session")
    if not token:
        raise creds_err
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email = payload.get("sub")
    except JWTError:
        raise creds_err
    user = get_user(email)
    if not user:
        raise creds_err
    return user


# ---------------------------------------------------------------- routes -----
@router.post("/register", response_model=Token, status_code=status.HTTP_201_CREATED)
def register(body: RegisterIn):
    email = validate_email(body.email)
    full_name = (body.full_name or "").strip()
    if len(full_name) < 2:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Please enter your full name")
    validate_password(body.password)
    if get_user(email):
        # Reveal duplication only on registration (standard UX); login stays generic.
        raise HTTPException(status.HTTP_409_CONFLICT, "An account with this email already exists")

    role = "admin" if count_users() == 0 else "user"   # first registered user is admin
    user = add_user(email, full_name, pwd.hash(body.password), role)
    return Token(access_token=_make_token(user), user=_user_out(user))


@router.post("/login", response_model=Token)
def login(body: LoginIn, request: Request):
    email = (body.email or "").strip().lower()
    # Lock out a specific ACCOUNT after repeated wrong passwords — never the whole
    # IP (on localhost every user shares 127.0.0.1, which would block everyone).
    email_key = f"em:{email}"
    _check_lock(email_key)

    user = get_user(email)
    if not user or not pwd.verify(body.password, user["hash"]):
        _record_failure(email_key, email, request)
        # Generic message — never reveal whether the email exists.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERR)

    _clear_failures(email_key)
    return Token(access_token=_make_token(user, body.remember), user=_user_out(user))


@router.get("/me", response_model=UserOut)
def me(user: dict = Depends(current_user)):
    return _user_out(user)


@router.post("/forgot-password")
def forgot_password(body: ForgotIn):
    """Emails a 6-digit reset code. Always returns the same generic success —
    so the response never reveals whether an email is registered."""
    generic = {"message": "If that email is registered, a reset code has been sent."}
    try:
        email = validate_email(body.email)
    except HTTPException:
        return generic

    user = get_user(email)
    if user:
        code = f"{secrets.randbelow(1_000_000):06d}"     # 6-digit code, zero-padded
        _CODES[email] = {
            "hash": _hash_token(code),
            "expires": time.time() + CODE_TTL_MIN * 60,
            "tries": 0,
        }
        email_utils.send_email(
            to=email,
            subject="Al-Wilayat — your password reset code",
            body=(
                f"As-salamu alaykum {user['full_name']},\n\n"
                "We received a request to reset your Al-Wilayat password.\n"
                f"Your reset code is:\n\n        {code}\n\n"
                f"Enter it in the app within {CODE_TTL_MIN} minutes to set a new password.\n"
                "If you did not request this, you can safely ignore this email."
            ),
        )
    return generic


@router.post("/reset-password")
def reset_password(body: ResetIn):
    email = (body.email or "").strip().lower()
    rec = _CODES.get(email)
    expired = HTTPException(status.HTTP_400_BAD_REQUEST,
                            "This code is invalid or has expired. Please request a new one.")
    if not rec or rec["expires"] <= time.time():
        _CODES.pop(email, None)
        raise expired
    if rec["tries"] >= CODE_MAX_TRIES:
        _CODES.pop(email, None)
        raise expired
    if _hash_token((body.code or "").strip()) != rec["hash"]:
        rec["tries"] += 1
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Incorrect code. Please check and try again.")

    validate_password(body.password)
    if not get_user(email):
        raise expired
    set_password(email, pwd.hash(body.password))
    _CODES.pop(email, None)                      # single-use code
    _clear_failures(f"em:{email}")               # unlock after a successful reset
    return {"message": "Your password has been updated. You can now sign in."}
