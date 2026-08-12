"""Password hashing, session tokens, OTP generation and phone handling.

Nothing secret is ever stored in clear text: passwords are bcrypt hashes,
OTPs and session tokens are peppered SHA-256 digests.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import re
import secrets

import bcrypt

from .config import settings

# --------------------------------------------------------------------------
# Passwords
# --------------------------------------------------------------------------


def _prehash(password: str) -> bytes:
    """bcrypt silently truncates at 72 bytes, so hash to a fixed length first."""
    digest = hashlib.sha256(password.encode("utf-8")).digest()
    return base64.b64encode(digest)


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_prehash(password), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    if not password or not password_hash:
        return False
    try:
        return bcrypt.checkpw(_prehash(password), password_hash.encode("utf-8"))
    except ValueError:
        return False


def password_problem(password: str) -> str | None:
    """Return a human-readable complaint, or None if the password is fine."""
    if len(password or "") < settings.MIN_PASSWORD_LENGTH:
        return f"Password must be at least {settings.MIN_PASSWORD_LENGTH} characters."
    if password.isdigit():
        return "Password cannot be only numbers."
    if password.lower() in {"password", "12345678", "qwertyui", "hackradar"}:
        return "That password is too common."
    return None


# --------------------------------------------------------------------------
# Usernames
# --------------------------------------------------------------------------

_USERNAME_RE = re.compile(r"^[a-z0-9._-]{3,30}$")


def normalize_username(raw: str) -> str:
    return (raw or "").strip().lower()


def username_problem(username: str) -> str | None:
    if not _USERNAME_RE.match(username or ""):
        return (
            "Username must be 3–30 characters, using letters, numbers, dot, "
            "underscore or hyphen."
        )
    return None


# --------------------------------------------------------------------------
# Phone numbers
# --------------------------------------------------------------------------


def normalize_phone(raw: str) -> str:
    """Normalise to E.164-ish. A bare 10-digit number gets the default code."""
    digits = re.sub(r"[^\d+]", "", raw or "")
    if not digits:
        return ""
    if digits.startswith("+"):
        return "+" + re.sub(r"\D", "", digits[1:])

    digits = re.sub(r"\D", "", digits)
    code = settings.DEFAULT_COUNTRY_CODE.lstrip("+")
    if digits.startswith("00"):
        return "+" + digits[2:]
    if len(digits) == 10:
        return f"+{code}{digits}"
    if digits.startswith(code):
        return f"+{digits}"
    return f"+{digits}"


def phone_problem(phone: str) -> str | None:
    if not re.match(r"^\+\d{8,15}$", phone or ""):
        return "Enter a valid phone number with country code, e.g. +91 98765 43210."
    return None


def mask_phone(phone: str) -> str:
    """'+919876543210' -> '+91 ••••• 43210'. Used outside the admin portal."""
    if not phone or len(phone) < 6:
        return phone or ""
    return f"{phone[:3]} ••••• {phone[-5:]}"


# --------------------------------------------------------------------------
# OTP + session tokens
# --------------------------------------------------------------------------


def generate_otp() -> str:
    """A cryptographically random numeric code of the configured length."""
    upper = 10 ** settings.OTP_LENGTH
    return str(secrets.randbelow(upper)).zfill(settings.OTP_LENGTH)


def hash_secret(value: str) -> str:
    """Peppered digest, used for OTP codes and session tokens alike."""
    return hmac.new(
        settings.SECRET_KEY.encode("utf-8"), (value or "").encode("utf-8"), hashlib.sha256
    ).hexdigest()


def verify_secret(value: str, expected_hash: str) -> bool:
    return hmac.compare_digest(hash_secret(value), expected_hash or "")


def generate_token() -> str:
    return secrets.token_urlsafe(32)
