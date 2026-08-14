"""Email delivery for one-time codes.

Codes go by email rather than SMS because email is free, unregulated for
this purpose, and reaches anyone — texting costs money everywhere and, for
Indian numbers, also requires DLT registration.

Three transports, auto-selected in order: Brevo, Resend, then SMTP.
Prefer the HTTP APIs in production — many hosts, Render'''s free tier
included, block outbound SMTP ports (25/465/587) to curb spam, so an
otherwise-correct Gmail setup simply times out there.

With nothing configured it prints the code to the server log, so the flow
still works in local development.
"""
from __future__ import annotations

import logging
import smtplib
from email.message import EmailMessage
from email.utils import formataddr

import httpx

from ..config import settings

log = logging.getLogger(__name__)


class SendResult:
    def __init__(self, delivered: bool, note: str = "", debug_code: str | None = None):
        self.delivered = delivered
        self.note = note[:240]
        #: Only set by the console fallback, so local testing needs no inbox.
        self.debug_code = debug_code


def active_provider() -> str:
    """Which transport to use.

    HTTP APIs are preferred over SMTP because many hosts — Render's free
    tier included — block outbound SMTP ports (25/465/587) to curb spam.
    An HTTPS API is unaffected by that.
    """
    explicit = (settings.EMAIL_PROVIDER or "").strip().lower()
    if explicit:
        return explicit
    if settings.BREVO_API_KEY:
        return "brevo"
    if settings.RESEND_API_KEY:
        return "resend"
    if settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD:
        return "smtp"
    return "console"


def is_configured() -> bool:
    return active_provider() != "console"


def provider_status() -> dict:
    provider = active_provider()
    configured = {
        "brevo": bool(settings.BREVO_API_KEY and settings.EMAIL_FROM),
        "resend": bool(settings.RESEND_API_KEY and settings.EMAIL_FROM),
        "smtp": bool(settings.SMTP_HOST and settings.SMTP_USER and settings.SMTP_PASSWORD),
        "console": True,
    }.get(provider, False)

    notes = {
        "brevo": "Live — codes are emailed over the Brevo HTTP API.",
        "resend": "Live — codes are emailed over the Resend HTTP API.",
        "smtp": (
            f"Live — codes are emailed via {settings.SMTP_HOST}. Note that many "
            "hosts block outbound SMTP ports; use an HTTP API provider if sends fail."
        ),
        "console": "Development mode — codes are printed to the backend log, not emailed.",
    }

    return {
        "provider": provider,
        "configured": configured,
        "is_live": provider != "console" and configured,
        "note": notes.get(provider, "Unknown provider"),
    }


_PURPOSE_TEXT = {
    "register": "confirm your email address and finish creating your HackRadar account",
    "reset": "reset your HackRadar password",
}


def send(to: str, subject: str, text: str, html: str) -> SendResult:
    """Send arbitrary email through whichever transport is configured.

    The shared dispatcher behind both send_otp (below) and
    notifier.dispatch — one provider selection, used everywhere mail goes
    out, so a working OTP send means a working deadline-alert send too.
    """
    provider = active_provider()
    if provider == "brevo":
        return _send_brevo(to, subject, text, html)
    if provider == "resend":
        return _send_resend(to, subject, text, html)
    if provider == "smtp":
        return _send_smtp(to, subject, text, html)

    log.info(
        "\n"
        "================ CONSOLE EMAIL (not sent) ================\n"
        "  to      : %s\n"
        "  subject : %s\n"
        "  ---\n"
        "%s\n"
        "  Configure an email provider to send for real.\n"
        "==========================================================",
        to,
        subject,
        text,
    )
    return SendResult(delivered=True, note="console provider — printed to the backend log, not emailed")


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

    if active_provider() == "console":
        # The OTP console path additionally echoes the code back to the
        # caller (so the login page can show it) — the one thing send()'s
        # generic console branch deliberately does not do.
        log.warning(
            "\n"
            "================ DEV CODE (no email sent) ================\n"
            "  to      : %s\n"
            "  purpose : %s\n"
            "  CODE    : %s\n"
            "  Configure an email provider to send for real.\n"
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

    return send(email, subject, text, html)


def _send_smtp(email: str, subject: str, text: str, html: str) -> SendResult:
    message = EmailMessage()
    message["From"] = formataddr((settings.EMAIL_FROM_NAME, settings.SMTP_FROM or settings.SMTP_USER))
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
    except OSError as exc:
        # Reached when the port is unreachable. Most PaaS free tiers block
        # outbound SMTP entirely, so say so rather than reporting a bare errno.
        log.exception("SMTP connection failed")
        return SendResult(
            False,
            f"Could not reach {settings.SMTP_HOST}:{settings.SMTP_PORT} ({exc}). "
            "Many hosts block outbound SMTP — use BREVO_API_KEY or RESEND_API_KEY instead.",
        )
    except Exception as exc:
        log.exception("Email delivery failed")
        return SendResult(False, f"Email delivery failed: {type(exc).__name__}: {exc}")


def _send_brevo(email: str, subject: str, text: str, html: str) -> SendResult:
    """Brevo's HTTP API — free tier sends 300 emails/day and needs no domain,
    only a verified sender address."""
    if not (settings.BREVO_API_KEY and settings.EMAIL_FROM):
        return SendResult(False, "Brevo selected but BREVO_API_KEY or EMAIL_FROM is missing")
    try:
        resp = httpx.post(
            "https://api.brevo.com/v3/smtp/email",
            headers={"api-key": settings.BREVO_API_KEY, "content-type": "application/json"},
            json={
                "sender": {"name": settings.EMAIL_FROM_NAME, "email": settings.EMAIL_FROM},
                "to": [{"email": email}],
                "subject": subject,
                "textContent": text,
                "htmlContent": html,
            },
            timeout=20,
        )
        if resp.status_code >= 400:
            detail = _api_error(resp)
            log.error("Brevo rejected the message: %s", detail)
            return SendResult(False, f"Brevo error: {detail}")
        return SendResult(True, "sent via Brevo")
    except Exception as exc:
        log.exception("Brevo request failed")
        return SendResult(False, f"Brevo request failed: {type(exc).__name__}")


def _send_resend(email: str, subject: str, text: str, html: str) -> SendResult:
    """Resend's HTTP API — 3,000 emails/month free, but sending to arbitrary
    recipients requires a verified domain."""
    if not (settings.RESEND_API_KEY and settings.EMAIL_FROM):
        return SendResult(False, "Resend selected but RESEND_API_KEY or EMAIL_FROM is missing")
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json={
                "from": f"{settings.EMAIL_FROM_NAME} <{settings.EMAIL_FROM}>",
                "to": [email],
                "subject": subject,
                "text": text,
                "html": html,
            },
            timeout=20,
        )
        if resp.status_code >= 400:
            detail = _api_error(resp)
            log.error("Resend rejected the message: %s", detail)
            return SendResult(False, f"Resend error: {detail}")
        return SendResult(True, "sent via Resend")
    except Exception as exc:
        log.exception("Resend request failed")
        return SendResult(False, f"Resend request failed: {type(exc).__name__}")


def _api_error(resp) -> str:
    try:
        body = resp.json()
        return str(body.get("message") or body.get("error") or body)[:180]
    except Exception:
        return resp.text[:180]


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
