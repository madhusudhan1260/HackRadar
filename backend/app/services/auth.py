"""Account lifecycle: OTP issue/verify, sessions, audit logging."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import AuthSession, LoginEvent, OtpCode, Profile, User
from ..security import (
    generate_otp,
    generate_token,
    hash_secret,
    verify_secret,
)
from . import sms


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _naive(value: datetime) -> datetime:
    """SQLite columns are naive; keep comparisons consistent."""
    return value.replace(tzinfo=None) if value.tzinfo else value


# --------------------------------------------------------------------------
# OTP
# --------------------------------------------------------------------------


class OtpError(Exception):
    def __init__(self, message: str, retry_after: int = 0):
        super().__init__(message)
        self.message = message
        self.retry_after = retry_after


def issue_otp(db: Session, user: User, purpose: str) -> dict:
    """Create and send a one-time code. Enforces cooldown and hourly cap."""
    now = _naive(utcnow())

    recent = db.scalars(
        select(OtpCode)
        .where(OtpCode.user_id == user.id, OtpCode.purpose == purpose)
        .order_by(OtpCode.created_at.desc())
        .limit(10)
    ).all()

    if recent:
        elapsed = (now - _naive(recent[0].created_at)).total_seconds()
        if elapsed < settings.OTP_RESEND_COOLDOWN_SECONDS:
            wait = int(settings.OTP_RESEND_COOLDOWN_SECONDS - elapsed)
            raise OtpError(f"Please wait {wait}s before requesting another code.", wait)

    hour_ago = now - timedelta(hours=1)
    if sum(1 for o in recent if _naive(o.created_at) > hour_ago) >= settings.OTP_HOURLY_LIMIT:
        raise OtpError("Too many codes requested. Try again in an hour.", 3600)

    # Any earlier unused code for this purpose is now void.
    for old in recent:
        if old.consumed_at is None:
            old.consumed_at = now

    code = generate_otp()
    result = sms.send_otp(user.phone, code, purpose)

    record = OtpCode(
        user_id=user.id,
        purpose=purpose,
        code_hash=hash_secret(code),
        sent_to=user.phone,
        expires_at=now + timedelta(minutes=settings.OTP_TTL_MINUTES),
        delivered=result.delivered,
        delivery_note=result.note,
    )
    db.add(record)
    db.commit()

    if not result.delivered:
        raise OtpError(f"Could not send the code: {result.note}")

    return {
        "sent": True,
        "expires_in": settings.OTP_TTL_MINUTES * 60,
        "resend_in": settings.OTP_RESEND_COOLDOWN_SECONDS,
        "note": result.note,
        # Populated only by the console provider so you can test without SMS.
        "dev_code": result.debug_code,
    }


def verify_otp(db: Session, user: User, purpose: str, code: str) -> None:
    """Raise OtpError unless `code` is the live code for this user+purpose."""
    now = _naive(utcnow())

    record = db.scalar(
        select(OtpCode)
        .where(
            OtpCode.user_id == user.id,
            OtpCode.purpose == purpose,
            OtpCode.consumed_at.is_(None),
        )
        .order_by(OtpCode.created_at.desc())
        .limit(1)
    )

    if record is None:
        raise OtpError("No code is pending. Request a new one.")
    if _naive(record.expires_at) < now:
        raise OtpError("That code has expired. Request a new one.")
    if record.attempts >= settings.OTP_MAX_ATTEMPTS:
        record.consumed_at = now
        db.commit()
        raise OtpError("Too many wrong attempts. Request a new code.")

    record.attempts += 1

    if not verify_secret((code or "").strip(), record.code_hash):
        remaining = settings.OTP_MAX_ATTEMPTS - record.attempts
        db.commit()
        if remaining <= 0:
            raise OtpError("Too many wrong attempts. Request a new code.")
        raise OtpError(f"Incorrect code. {remaining} attempt(s) left.")

    record.consumed_at = now
    db.commit()


# --------------------------------------------------------------------------
# Sessions
# --------------------------------------------------------------------------


def create_session(db: Session, user: User, request: Request | None = None) -> str:
    """Issue a session token. Only the hash is stored server-side."""
    token = generate_token()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_secret(token),
            expires_at=_naive(utcnow()) + timedelta(hours=settings.SESSION_TTL_HOURS),
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
    )

    user.last_login_at = _naive(utcnow())
    user.login_count += 1
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()
    return token


def resolve_session(db: Session, token: str) -> User | None:
    if not token:
        return None
    record = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_secret(token))
    )
    if record is None or record.revoked_at is not None:
        return None
    if _naive(record.expires_at) < _naive(utcnow()):
        return None

    record.last_seen_at = _naive(utcnow())
    db.commit()

    user = db.get(User, record.user_id)
    return user if user and user.status == "active" else None


def revoke_session(db: Session, token: str) -> None:
    record = db.scalar(
        select(AuthSession).where(AuthSession.token_hash == hash_secret(token))
    )
    if record and record.revoked_at is None:
        record.revoked_at = _naive(utcnow())
        db.commit()


def revoke_all_sessions(db: Session, user_id: int) -> int:
    records = db.scalars(
        select(AuthSession).where(
            AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None)
        )
    ).all()
    now = _naive(utcnow())
    for record in records:
        record.revoked_at = now
    db.commit()
    return len(records)


# --------------------------------------------------------------------------
# Audit + profile
# --------------------------------------------------------------------------


def log_event(
    db: Session,
    event: str,
    success: bool,
    user: User | None = None,
    username_tried: str = "",
    reason: str = "",
    request: Request | None = None,
) -> None:
    db.add(
        LoginEvent(
            user_id=user.id if user else None,
            username_tried=(username_tried or (user.username if user else ""))[:60],
            event=event,
            success=success,
            reason=reason[:120],
            ip=_client_ip(request),
            user_agent=_user_agent(request),
        )
    )
    db.commit()


def ensure_profile(db: Session, user: User) -> Profile:
    """Every account gets its own profile, bookmarks and match scores."""
    profile = db.scalar(select(Profile).where(Profile.user_id == user.id))
    if profile is None:
        from ..routers.profile import DEFAULT_INTERESTS, DEFAULT_SKILLS

        profile = Profile(
            user_id=user.id,
            name=user.name,
            skills=list(DEFAULT_SKILLS),
            interests=list(DEFAULT_INTERESTS),
            notify_days_before=[7, 3, 1],
        )
        db.add(profile)
        db.commit()
        db.refresh(profile)
    return profile


def _client_ip(request: Request | None) -> str:
    if request is None:
        return ""
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()[:60]
    return (request.client.host if request.client else "")[:60]


def _user_agent(request: Request | None) -> str:
    return (request.headers.get("user-agent", "") if request else "")[:300]
