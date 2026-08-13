"""Registration, login, and password recovery.

Flow:

  Register  -> details -> one-time code emailed -> verified & signed in.
               This is the ONLY time a normal user sees a signup code.
  Login     -> username + password. No code.
  Forgot    -> code emailed to the registered address -> new password.

Passwords are stored as bcrypt hashes and are never recoverable. "Recovery"
always means setting a new one.

Codes go by email rather than SMS: email costs nothing, has no per-country
regulatory hurdle, and reaches anyone. Codes are stored hashed, expire
quickly, and are rate limited — OTP endpoints attract abuse.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import AuthSession, OtpCode, Profile, User
from ..schemas import (
    AuthOut,
    ForgotStartIn,
    LoginIn,
    OtpSentOut,
    RegisterIn,
    ResetPasswordIn,
    UserOut,
    VerifyOtpIn,
)
from ..security import (
    email_problem,
    hash_password,
    mask_email,
    mask_phone,
    normalize_email,
    normalize_phone,
    normalize_username,
    password_problem,
    phone_problem,
    username_problem,
    verify_password,
)
from ..services import auth as auth_service
from ..services.auth import OtpError

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Lock an account briefly after repeated wrong passwords.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15
# How long an unverified registration holds its username, email and phone.
PENDING_TTL_HOURS = 24


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        name=user.name,
        email=user.email or "",
        phone_masked=mask_phone(user.phone),
        role=user.role,
        status=user.status,
        phone_verified=user.phone_verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        login_count=user.login_count,
    )


def _otp_response(user: User, result: dict) -> OtpSentOut:
    return OtpSentOut(
        sent=True,
        sent_to_masked=mask_email(user.email or ""),
        expires_in=result["expires_in"],
        resend_in=result["resend_in"],
        note=result.get("note", ""),
        dev_code=result.get("dev_code"),
        support_email=settings.SUPPORT_EMAIL,
    )


def _purge_user(db: Session, user: User) -> None:
    """Delete a user and everything hanging off them.

    Rows are removed explicitly rather than relying on ON DELETE CASCADE:
    SQLite reuses primary keys, so an orphaned code row would otherwise be
    inherited by whoever gets that id next.
    """
    for model in (OtpCode, AuthSession):
        for row in db.scalars(select(model).where(model.user_id == user.id)).all():
            db.delete(row)
    for profile in db.scalars(select(Profile).where(Profile.user_id == user.id)).all():
        db.delete(profile)
    db.delete(user)
    db.commit()


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


@router.post("/register", response_model=OtpSentOut, status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    """Create a pending account and email the verification code."""
    username = normalize_username(payload.username)
    phone = normalize_phone(payload.phone)
    email = normalize_email(payload.email)
    name = payload.name.strip()

    for problem in (
        username_problem(username),
        email_problem(email),
        phone_problem(phone),
        password_problem(payload.password),
    ):
        if problem:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    if db.scalar(select(User).where(User.username == username)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken.")

    if db.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That email address is already registered. Try signing in instead.",
        )

    existing_phone = db.scalar(select(User).where(User.phone == phone))
    if existing_phone is not None:
        stale = (
            existing_phone.status == "pending"
            and (_naive_now() - existing_phone.created_at) > timedelta(hours=PENDING_TTL_HOURS)
        )
        if stale:
            # Long-abandoned signup that never verified — safe to clear out.
            _purge_user(db, existing_phone)
        elif existing_phone.status == "pending":
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "That phone number has a registration waiting for verification. "
                "Finish it with the code we sent, or request a new code.",
            )
        else:
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                "That phone number is already registered. Try signing in instead.",
            )

    user = User(
        username=username,
        name=name,
        phone=phone,
        email=email,
        password_hash=hash_password(payload.password),
        role="user",
        status="pending",
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    try:
        result = auth_service.issue_otp(db, user, "register")
    except OtpError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, exc.message) from None

    auth_service.log_event(db, "register", True, user=user, reason="code sent", request=request)
    return _otp_response(user, result)


@router.post("/verify-otp", response_model=AuthOut)
def verify_registration(payload: VerifyOtpIn, request: Request, db: Session = Depends(get_db)):
    """Confirm the email, activate the account, and sign the user in."""
    username = normalize_username(payload.username)
    user = db.scalar(select(User).where(User.username == username))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account.")
    if user.status == "active":
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST, "This account is already verified. Please sign in."
        )

    try:
        auth_service.verify_otp(db, user, "register", payload.code)
    except OtpError as exc:
        auth_service.log_event(db, "register", False, user=user, reason=exc.message, request=request)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from None

    user.status = "active"
    user.email_verified = True
    db.commit()

    auth_service.ensure_profile(db, user)
    token = auth_service.create_session(db, user, request)
    auth_service.log_event(db, "register", True, user=user, reason="verified", request=request)

    return AuthOut(token=token, user=to_user_out(user))


@router.post("/resend-otp", response_model=OtpSentOut)
def resend_otp(payload: ForgotStartIn, db: Session = Depends(get_db)):
    """Resend the signup code. Rate limited by the OTP service."""
    user = db.scalar(select(User).where(User.username == normalize_username(payload.username)))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such account.")
    if user.status == "active":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "This account is already verified.")

    try:
        result = auth_service.issue_otp(db, user, "register")
    except OtpError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, exc.message) from None
    return _otp_response(user, result)


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
    """Username + password. Verified users never see a code here."""
    username = normalize_username(payload.username)
    user = db.scalar(select(User).where(User.username == username))

    if user is None:
        auth_service.log_event(
            db, "login", False, username_tried=username, reason="unknown username", request=request
        )
        # Same message either way, so the form can't be used to enumerate users.
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")

    if user.locked_until and user.locked_until > _naive_now():
        wait = int((user.locked_until - _naive_now()).total_seconds() // 60) + 1
        auth_service.log_event(db, "login", False, user=user, reason="locked", request=request)
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Too many failed attempts. Try again in {wait} minute(s), or reset your password.",
        )

    if not verify_password(payload.password, user.password_hash):
        user.failed_attempts += 1
        reason = "wrong password"
        if user.failed_attempts >= MAX_FAILED_ATTEMPTS:
            user.locked_until = _naive_now() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_attempts = 0
            reason = "locked after repeated failures"
        db.commit()
        auth_service.log_event(db, "login", False, user=user, reason=reason, request=request)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Incorrect username or password.")

    if user.status == "pending":
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "Your email address is not verified yet. Finish registration to continue.",
        )
    if user.status == "blocked":
        auth_service.log_event(db, "login", False, user=user, reason="blocked", request=request)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been blocked.")

    # The Admin tab is a separate door: the password was right, but this
    # account has no admin rights, so refuse instead of signing them in.
    if payload.as_admin and user.role != "admin":
        auth_service.log_event(db, "login", False, user=user, reason="not an admin", request=request)
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "This account does not have admin access. Use the User tab to sign in.",
        )

    auth_service.ensure_profile(db, user)
    token = auth_service.create_session(db, user, request)
    auth_service.log_event(db, "login", True, user=user, request=request)

    return AuthOut(token=token, user=to_user_out(user))


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)):
    header = request.headers.get("authorization", "")
    token = header[7:] if header.lower().startswith("bearer ") else ""
    if token:
        user = auth_service.resolve_session(db, token)
        auth_service.revoke_session(db, token)
        if user:
            auth_service.log_event(db, "logout", True, user=user, request=request)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return to_user_out(user)


# --------------------------------------------------------------------------
# Forgot password — self service, by SMS
# --------------------------------------------------------------------------


@router.post("/forgot-password", response_model=OtpSentOut)
def forgot_password(payload: ForgotStartIn, request: Request, db: Session = Depends(get_db)):
    """Email a reset code to the address registered on the account."""
    user = db.scalar(select(User).where(User.username == normalize_username(payload.username)))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account with that username.")
    if user.status == "blocked":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been blocked.")

    try:
        result = auth_service.issue_otp(db, user, "reset")
    except OtpError as exc:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, exc.message) from None

    auth_service.log_event(db, "reset", True, user=user, reason="code sent", request=request)
    return _otp_response(user, result)


@router.post("/reset-password", response_model=AuthOut)
def reset_password(payload: ResetPasswordIn, request: Request, db: Session = Depends(get_db)):
    """Verify the reset code and set a new password."""
    user = db.scalar(select(User).where(User.username == normalize_username(payload.username)))
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No account with that username.")

    problem = password_problem(payload.new_password)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    try:
        auth_service.verify_otp(db, user, "reset", payload.code)
    except OtpError as exc:
        auth_service.log_event(db, "reset", False, user=user, reason=exc.message, request=request)
        raise HTTPException(status.HTTP_400_BAD_REQUEST, exc.message) from None

    user.password_hash = hash_password(payload.new_password)
    user.failed_attempts = 0
    user.locked_until = None
    # Completing a reset also proves the user holds the inbox.
    if user.status == "pending":
        user.status = "active"
        user.email_verified = True
    db.commit()

    # Anyone holding an old session is signed out — standard after a reset.
    auth_service.revoke_all_sessions(db, user.id)

    auth_service.ensure_profile(db, user)
    token = auth_service.create_session(db, user, request)
    auth_service.log_event(db, "reset", True, user=user, reason="password changed", request=request)

    return AuthOut(token=token, user=to_user_out(user))


@router.get("/check-username")
def check_username(username: str, db: Session = Depends(get_db)):
    """Live availability check for the signup form."""
    candidate = normalize_username(username)
    problem = username_problem(candidate)
    if problem:
        return {"username": candidate, "available": False, "reason": problem}
    taken = db.scalar(select(User).where(User.username == candidate)) is not None
    return {
        "username": candidate,
        "available": not taken,
        "reason": "That username is already taken." if taken else "",
    }
