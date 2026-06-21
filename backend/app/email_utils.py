"""Tiny e-mail helper for Al-Wilayat auth.

Sends real mail through SMTP when SMTP_HOST is configured; otherwise it just
logs the message so the password-reset link is visible during local
development (you never need a mail server to test the flow).

Configure via backend/.env:
    SMTP_HOST, SMTP_PORT (default 587), SMTP_USER, SMTP_PASS,
    SMTP_FROM (default SMTP_USER), SMTP_TLS (1/0, default 1)
    ADMIN_ALERT_EMAIL  -> where failed-login alerts are sent
"""
import logging
import os
import smtplib
from email.message import EmailMessage

log = logging.getLogger("wilayat.mail")

ADMIN_ALERT_EMAIL = os.getenv("ADMIN_ALERT_EMAIL", "haffeypythonista@gmail.com")


def _smtp_configured() -> bool:
    return bool(os.getenv("SMTP_HOST"))


def send_email(to: str, subject: str, body: str) -> bool:
    """Send one plain-text e-mail. Returns True if actually dispatched.

    With no SMTP configured the mail is logged (dev mode) and we return False
    so callers know it was not really sent — but the flow still succeeds.
    """
    if not _smtp_configured():
        log.warning("[DEV-EMAIL] (no SMTP configured)\n  To: %s\n  Subject: %s\n  %s",
                    to, subject, body)
        return False

    host = os.environ["SMTP_HOST"]
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER", "")
    password = os.getenv("SMTP_PASS", "")
    # Mail is sent from the owner's address by default.
    sender = os.getenv("SMTP_FROM") or user or "haffeypythonista@gmail.com"
    use_tls = os.getenv("SMTP_TLS", "1") not in ("0", "false", "False")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(body)

    try:
        with smtplib.SMTP(host, port, timeout=15) as server:
            if use_tls:
                server.starttls()
            if user:
                server.login(user, password)
            server.send_message(msg)
        log.info("Sent e-mail to %s (%s)", to, subject)
        return True
    except Exception as e:  # noqa: BLE001 — never let mail break the request
        log.error("E-mail send failed (%s): %s", to, e)
        return False


def send_admin_alert(attempted_email: str, ip: str, user_agent: str, when: str) -> None:
    """Notify the admin about repeated failed login attempts."""
    body = (
        "Security alert — repeated failed login attempts on Al-Wilayat.\n\n"
        f"  Attempted email : {attempted_email}\n"
        f"  Time (UTC)      : {when}\n"
        f"  IP address      : {ip or 'unknown'}\n"
        f"  Browser/device  : {user_agent or 'unknown'}\n\n"
        "If this was not you, no action is needed — the account is rate-limited."
    )
    send_email(ADMIN_ALERT_EMAIL, "⚠️ Al-Wilayat — failed login attempts", body)
