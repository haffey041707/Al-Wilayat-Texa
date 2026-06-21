# Al-Wilayat — Authentication

A complete, production-shaped Sign In / Sign Up / Password-Reset system for the
Al-Wilayat Shia Islamic app. Premium Islamic UI (navy + white + gold), secure
FastAPI backend, no plain-text passwords.

## File structure
```
web/
├── auth.html            # Sign In / Sign Up / Forgot / Reset / Profile (one page, switched views)
├── css/auth.css         # Premium Islamic theme — navy/white/gold, geometric pattern, responsive
└── js/auth.js           # Validation, password strength, show/hide, API calls, session

backend/app/
├── auth.py              # Register, login, /me, forgot-password, reset-password (JWT + bcrypt)
└── email_utils.py       # SMTP sender (logs the reset link in dev when no SMTP set)
```

## Run it
```bash
# 1) Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env           # set WILAYAT_SECRET (and SMTP_* for real email)
python3 -m uvicorn app.main:app --reload     # → http://localhost:8000

# 2) Frontend
cd web
python3 -m http.server 5500    # → http://localhost:5500/auth.html
```
Open **http://localhost:5500/auth.html**. Without a mail server, the password-reset
link is printed to the backend console (look for `[DEV-EMAIL]`), so you can test the
full flow locally.

## Endpoints (`/api/auth`)
| Method | Path | Body | Purpose |
|---|---|---|---|
| POST | `/register` | full_name, email, password | Create account → JWT + user |
| POST | `/login` | email, password, remember | Sign in → JWT + user |
| GET  | `/me` | (Bearer token) | Current user profile |
| POST | `/forgot-password` | email | Always generic 200; emails a reset link if registered |
| GET  | `/reset/validate?token=` | — | Is a reset token still valid? |
| POST | `/reset-password` | token, password | Set a new password |

## Password policy (enforced on client **and** server)
≥ 8 characters, with at least one uppercase, one lowercase, one number, and one
special character. Each user sets their own password; stored only as a bcrypt hash.

## Security features
- **bcrypt** password hashing (never plain text)
- **JWT** access tokens; 12 h normally, 30 days with "Remember me"
- **Rate limiting / brute-force lockout** per IP and per email (5 fails / 15 min → 15 min lock)
- **Admin alert email** on repeated failures → `ADMIN_ALERT_EMAIL` (default haffeypythonista@gmail.com),
  including attempted email, time, IP and browser/device
- **Secure reset tokens** — random, hashed at rest, single-use, 30-min expiry
- **No email enumeration** — login and forgot-password never reveal whether an email exists
- **Input validation** on every field; HTTPS-ready (set real `WILAYAT_SECRET` + serve over TLS)

## Production notes
The demo keeps users and reset tokens in memory (`_USERS`, `_RESETS` in `auth.py`).
Swap these for a database (e.g. PostgreSQL) — the function boundaries are already
DB-shaped. Set a strong `WILAYAT_SECRET`, configure SMTP, and serve behind HTTPS.
