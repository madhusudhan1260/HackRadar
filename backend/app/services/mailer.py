"""Email delivery for one-time codes.

Uses plain SMTP, which every provider supports and which costs nothing —
a Gmail account with an App Password sends ~500 messages a day for free.
That is the reason codes go to email rather than SMS: texting has a
per-message cost everywhere, and business SMS to Indian numbers also needs
DLT registration.

With no SMTP credentials configured it falls back to printing the code to
the server log, so the whole flow still works in local development.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

from ..config import settings

log = logging.getLogger(__name__)


class SendResult:
    def __init__(self, delivered: bool, note: str = "", debug_code: str | None = None):
        self.delivered = delivered
        self.note = note[:240]
        #: Only set by the console fallback, so local testing needs no inbox.
        self.debug_code = debug_code


def is_configured() -> bool:
    return bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD)


def provider_status() -> dict:
    configured = is_configured()
    return {
        "provider": "smtp" if configured else "console",
        "configured": configured,
        "is_live": configured,
        "note": (
            f"Live — codes are emailed via {settings.SMTP_HOST}."
            if configured
            else "Development mode — codes are printed to the backend log, not emailed."
        ),
    }


_PURPOSE_TEXT = {
    "register": "confirm your email address and finish creating your HackRadar account",
    "reset": "reset your HackRadar password",
}


def send_otp(email: str, code: str, purpose: str) -> SendResult:
    reason = _PURPOSE_TEXT.get(purpose, "verify your HackRadar account")
    minutes = settings.OTP_TTL_MINUTES

    subject = f"{code} is your HackRadar code"
    text = (
        f"Your HackRadar verification code is:\n\n"
        f"    {code}\n\n"
        f"Use it to {reason}. It expires in {minutes} minutes.\n\n"
        f"If you did not request this, you can ignore this email — "
        f"nothing will change on your account.\n\n"
        f"— HackRadar"
    )
    html = _html_body(code, reason, minutes)

    if not is_configured():
        log.warning(
            "\n"
            "================ DEV CODE (no email sent) ================\n"
            "  to      : %s\n"
            "  purpose : %s\n"
            "  CODE    : %s\n"
            "  Set SMTP_* in .env to send real email.\n"
            "==========================================================",
            email,
            purpose,
            code,
        )
        return SendResult(
            delivered=True,
            note="console provider — code printed to the server log, no email sent",
            debug_code=code,
        )

    message = EmailMessage()
    message["From"] = formataddr(("HackRadar", settings.SMTP_FROM or settings.SMTP_USER))
    message["To"] = email
    message["Subject"] = subject
    message.set_content(text)
    message.add_alternative(html, subtype="html")

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.starttls()
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        return SendResult(True, f"sent via {settings.SMTP_HOST}")
    except smtplib.SMTPAuthenticationError:
        log.exception("SMTP authentication failed")
        return SendResult(
            False,
            "SMTP login rejected. For Gmail use a 16-character App Password, "
            "not your account password.",
        )
    except Exception as exc:
        log.exception("Email delivery failed")
        return SendResult(False, f"Email delivery failed: {type(exc).__name__}")


def _html_body(code: str, reason: str, minutes: int) -> str:
    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#0a0e17;font-family:-apple-system,
               BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e8edf5;">
    <div style="max-width:440px;margin:0 auto;background:#111827;border:1px solid #1f2a3d;
                border-radius:16px;padding:28px;">
      <h1 style="margin:0 0 6px;font-size:19px;">📡 HackRadar</h1>
      <p style="margin:0 0 22px;color:#64748b;font-size:13px;">
        One place for every hackathon
      </p>

      <p style="margin:0 0 14px;color:#94a3b8;font-size:14px;">
        Use this code to {reason}:
      </p>

      <div style="font-size:34px;font-weight:800;letter-spacing:10px;text-align:center;
                  padding:18px;background:#161f31;border-radius:12px;color:#a5b4fc;">
        {code}
      </div>

      <p style="margin:18px 0 0;color:#64748b;font-size:12.5px;line-height:1.6;">
        It expires in {minutes} minutes. If you did not request this, ignore this
        email — nothing will change on your account.
      </p>
    </div>
  </body>
</html>"""
