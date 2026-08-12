"""SMS delivery for OTP codes.

Three providers, chosen with SMS_PROVIDER in .env:

  console  (default)  Prints the OTP to the backend log. Development only —
                      no SMS is sent and no account is needed.
  twilio              Real SMS via Twilio's REST API.
  msg91               Real SMS via MSG91, which is usually cheaper for
                      Indian numbers and handles DLT templates.

Switching providers needs no code change, only credentials.
"""
from __future__ import annotations

import logging

import httpx

from ..config import settings

log = logging.getLogger(__name__)


class SmsResult:
    def __init__(self, delivered: bool, note: str = "", debug_code: str | None = None):
        self.delivered = delivered
        self.note = note[:240]
        #: Only ever populated by the console provider, so the dev UI can
        #: show the code without a real phone. Never set in production.
        self.debug_code = debug_code


def send_otp(phone: str, code: str, purpose: str) -> SmsResult:
    message = (
        f"{code} is your HackRadar verification code. "
        f"It expires in {settings.OTP_TTL_MINUTES} minutes. Do not share it with anyone."
    )
    provider = settings.SMS_PROVIDER

    if provider == "twilio":
        return _send_twilio(phone, message)
    if provider == "msg91":
        return _send_msg91(phone, code, message)
    return _send_console(phone, code, purpose, message)


# --------------------------------------------------------------------------


def _send_console(phone: str, code: str, purpose: str, message: str) -> SmsResult:
    log.warning(
        "\n"
        "===================== DEV OTP (no SMS sent) =====================\n"
        "  to      : %s\n"
        "  purpose : %s\n"
        "  CODE    : %s\n"
        "  Set SMS_PROVIDER=twilio or msg91 in .env to send real SMS.\n"
        "=================================================================",
        phone,
        purpose,
        code,
    )
    return SmsResult(
        delivered=True,
        note="console provider — code printed to the server log, no SMS sent",
        debug_code=code,
    )


def _send_twilio(phone: str, message: str) -> SmsResult:
    if not (settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER):
        return SmsResult(False, "Twilio selected but TWILIO_* credentials are missing")

    url = (
        f"https://api.twilio.com/2010-04-01/Accounts/"
        f"{settings.TWILIO_ACCOUNT_SID}/Messages.json"
    )
    try:
        resp = httpx.post(
            url,
            auth=(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN),
            data={"To": phone, "From": settings.TWILIO_FROM_NUMBER, "Body": message},
            timeout=20,
        )
        if resp.status_code >= 400:
            detail = resp.json().get("message", resp.text[:150])
            log.error("Twilio rejected the message: %s", detail)
            return SmsResult(False, f"Twilio error: {detail}")
        return SmsResult(True, "sent via Twilio")
    except Exception as exc:
        log.exception("Twilio request failed")
        return SmsResult(False, f"Twilio request failed: {type(exc).__name__}")


def _send_msg91(phone: str, code: str, message: str) -> SmsResult:
    if not settings.MSG91_AUTH_KEY:
        return SmsResult(False, "MSG91 selected but MSG91_AUTH_KEY is missing")

    # MSG91 wants the number without the leading '+'.
    to = phone.lstrip("+")

    try:
        if settings.MSG91_TEMPLATE_ID:
            # DLT-approved template flow — required for Indian numbers.
            resp = httpx.post(
                "https://control.msg91.com/api/v5/flow/",
                headers={"authkey": settings.MSG91_AUTH_KEY, "Content-Type": "application/json"},
                json={
                    "template_id": settings.MSG91_TEMPLATE_ID,
                    "sender": settings.MSG91_SENDER_ID,
                    "recipients": [{"mobiles": to, "otp": code}],
                },
                timeout=20,
            )
        else:
            resp = httpx.get(
                "https://control.msg91.com/api/v5/otp",
                params={
                    "authkey": settings.MSG91_AUTH_KEY,
                    "mobile": to,
                    "otp": code,
                    "sender": settings.MSG91_SENDER_ID,
                    "otp_expiry": settings.OTP_TTL_MINUTES,
                },
                timeout=20,
            )

        payload = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code >= 400 or str(payload.get("type", "")).lower() == "error":
            detail = payload.get("message") or resp.text[:150]
            log.error("MSG91 rejected the message: %s", detail)
            return SmsResult(False, f"MSG91 error: {detail}")
        return SmsResult(True, "sent via MSG91")
    except Exception as exc:
        log.exception("MSG91 request failed")
        return SmsResult(False, f"MSG91 request failed: {type(exc).__name__}")


def send_test(phone: str) -> SmsResult:
    """Send a real (non-OTP) message to prove the provider is wired up."""
    return {
        "twilio": lambda: _send_twilio(phone, _TEST_BODY),
        "msg91": lambda: _send_msg91(phone, "123456", _TEST_BODY),
    }.get(
        settings.SMS_PROVIDER,
        lambda: _send_console(phone, "------", "test", _TEST_BODY),
    )()


_TEST_BODY = "HackRadar test message. If you received this, SMS delivery is working."


def provider_status() -> dict:
    """Shown in the admin portal so misconfiguration is obvious."""
    provider = settings.SMS_PROVIDER
    if provider == "twilio":
        configured = bool(
            settings.TWILIO_ACCOUNT_SID and settings.TWILIO_AUTH_TOKEN and settings.TWILIO_FROM_NUMBER
        )
    elif provider == "msg91":
        configured = bool(settings.MSG91_AUTH_KEY)
    else:
        configured = True

    return {
        "provider": provider,
        "configured": configured,
        "is_live": provider in ("twilio", "msg91") and configured,
        "note": {
            "console": "Development mode — OTPs are printed to the backend log, not sent by SMS.",
            "twilio": "Live SMS via Twilio.",
            "msg91": "Live SMS via MSG91.",
        }.get(provider, "Unknown provider"),
    }
