"""Registration, login, and password recovery.

Flow:

  Register  -> details -> one-time code emailed -> verified & signed in.
               This is the ONLY time a normal user sees a signup code.
  Login     -> username + password. No code.
  Forgot    -> code emailed to the registered address -> new password.

One email address may hold several accounts — usernames are what identify
people here. Recovery is therefore keyed on username: the code proves you
hold the inbox, the username says which account to act on.

Passwords are stored as bcrypt hashes and are never recoverable. "Recovery"
always means setting a new one.

Codes go by email rather than SMS: email costs nothing, has no per-country
regulatory hurdle, and reaches anyone. Codes are stored hashed, expire
quickly, and are rate limited — OTP endpoints attract abuse.
"""
from __future__ import annotations

import hashlib
import re
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import RedirectResponse
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


@router.get("/oauth/providers")
def oauth_providers():
    """Which OAuth providers actually have credentials configured — the
    frontend hides buttons for anything not in this list."""
    from ..services import oauth

    return {"providers": oauth.configured_providers()}


@router.get("/oauth/{provider}/start")
def oauth_start(provider: str):
    """Redirect the browser to the provider's own consent screen."""
    from ..services import oauth

    if provider not in oauth.PROVIDERS:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Unknown sign-in provider.")
    if provider not in oauth.configured_providers():
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            f"{provider.title()} sign-in is not configured yet.",
        )
    return RedirectResponse(oauth.authorize_url(provider, oauth.make_state()))


@router.get("/oauth/{provider}/callback")
def oauth_callback(
    provider: str,
    request: Request,
    db: Session = Depends(get_db),
    code: str = "",
    state: str = "",
    error: str = "",
):
    """Where the provider redirects back to. Never returns JSON — this is a
    top-level browser navigation, so the outcome (a token, or an error) is
    handed to the frontend as a query param on a redirect, and Login.jsx
    picks it up from there."""
    from ..services import oauth

    def fail(message: str) -> RedirectResponse:
        return RedirectResponse(f"{settings.OAUTH_FRONTEND_URL}/?oauth_error={quote(message)}")

    if provider not in oauth.PROVIDERS:
        return fail("Unknown sign-in provider.")
    if error:
        return fail("Sign-in was cancelled.")
    if not code or not state or not oauth.verify_state(state):
        return fail("Sign-in request expired — try again.")

    try:
        info = oauth.exchange_code(provider, code)
    except Exception:
        return fail(f"{provider.title()} sign-in failed. Try again.")

    user = db.scalar(
        select(User).where(
            User.oauth_provider == provider, User.oauth_subject == info.subject
        )
    )

    # Same verified email, no OAuth linked yet: treat this as "the same
    # person signing in a new way" rather than creating a second account.
    if user is None and info.email:
        candidate = db.scalar(
            select(User).where(
                User.email == normalize_email(info.email), User.oauth_provider == ""
            )
        )
        if candidate is not None and candidate.status == "active":
            candidate.oauth_provider = provider
            candidate.oauth_subject = info.subject
            candidate.email_verified = True
            user = candidate

    if user is None:
        base = normalize_username(
            (info.email.split("@")[0] if info.email else "") or info.name or f"{provider}user"
        )
        base = re.sub(r"[^a-z0-9._-]", "", base)[:26] or f"{provider}user"
        username = base
        suffix = 1
        while db.scalar(select(User).where(User.username == username)) is not None:
            suffix += 1
            username = f"{base}{suffix}"[:30]

        # No phone comes from either provider. A synthetic, unique
        # placeholder keeps the (unique, not-null) column happy without
        # pretending to be a real number anyone could call.
        placeholder_phone = "oauth" + hashlib.sha1(
            f"{provider}:{info.subject}".encode()
        ).hexdigest()[:18]

        user = User(
            username=username,
            name=info.name or username,
            phone=placeholder_phone,
            email=normalize_email(info.email) if info.email else None,
            email_verified=bool(info.email),
            # A random password nobody knows — password login always fails
            # for this account, which is correct: it only signs in via OAuth.
            password_hash=hash_password(secrets.token_urlsafe(32)),
            oauth_provider=provider,
            oauth_subject=info.subject,
            role="user",
            status="active",
            phone_verified=False,
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    if user.status != "active":
        return fail("This account is not active. Contact support.")

    auth_service.ensure_profile(db, user)
    token = auth_service.create_session(db, user, request)
    auth_service.log_event(db, "login", True, user=user, reason=f"oauth:{provider}", request=request)

    return RedirectResponse(f"{settings.OAUTH_FRONTEND_URL}/?oauth_token={token}")


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
