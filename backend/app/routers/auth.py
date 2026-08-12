"""Registration, login, and password recovery.

Flow:

  Register  -> name, unique username, phone, password. The account is
               active immediately; there is no phone verification step.
  Login     -> username + password.
  Forgot    -> the user is told to email the admin, who resets the
               password from the admin portal. There is no self-service
               reset, so no code is ever sent.

Passwords are stored as bcrypt hashes and are never recoverable — not by
the user, not by the admin, not by this code. Recovery means *setting a
new one*, which is what the admin portal does.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import (
    AuthOut,
    ForgotStartIn,
    LoginIn,
    RegisterIn,
    SupportInfoOut,
    UserOut,
)
from ..security import (
    hash_password,
    mask_phone,
    normalize_phone,
    normalize_username,
    password_problem,
    phone_problem,
    username_problem,
    verify_password,
)
from ..services import auth as auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Lock an account briefly after repeated wrong passwords.
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_MINUTES = 15


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def to_user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        name=user.name,
        phone_masked=mask_phone(user.phone),
        role=user.role,
        status=user.status,
        phone_verified=user.phone_verified,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
        login_count=user.login_count,
    )


# --------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------


@router.post("/register", response_model=AuthOut, status_code=201)
def register(payload: RegisterIn, request: Request, db: Session = Depends(get_db)):
    """Create an account and sign the user straight in."""
    username = normalize_username(payload.username)
    phone = normalize_phone(payload.phone)
    name = payload.name.strip()

    for problem in (
        username_problem(username),
        phone_problem(phone),
        password_problem(payload.password),
    ):
        if problem:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    if db.scalar(select(User).where(User.username == username)) is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "That username is already taken.")

    if db.scalar(select(User).where(User.phone == phone)) is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "That phone number is already registered. Try signing in instead.",
        )

    user = User(
        username=username,
        name=name,
        phone=phone,
        password_hash=hash_password(payload.password),
        role="user",
        status="active",
        # No OTP step, so the number is recorded but not proven.
        phone_verified=False,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    auth_service.ensure_profile(db, user)
    token = auth_service.create_session(db, user, request)
    auth_service.log_event(db, "register", True, user=user, reason="account created", request=request)

    return AuthOut(token=token, user=to_user_out(user))


# --------------------------------------------------------------------------
# Login
# --------------------------------------------------------------------------


@router.post("/login", response_model=AuthOut)
def login(payload: LoginIn, request: Request, db: Session = Depends(get_db)):
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
            f"Too many failed attempts. Try again in {wait} minute(s), or use "
            "'Forgot password' to contact the admin.",
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

    if user.status == "blocked":
        auth_service.log_event(db, "login", False, user=user, reason="blocked", request=request)
        raise HTTPException(status.HTTP_403_FORBIDDEN, "This account has been blocked.")

    # The Admin tab is a separate door: the password was right, but this
    # account has no admin rights, so refuse instead of signing them in.
    if payload.as_admin and user.role != "admin":
        auth_service.log_event(
            db, "login", False, user=user, reason="not an admin", request=request
        )
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
# Password recovery — admin assisted
# --------------------------------------------------------------------------


@router.post("/forgot-password", response_model=SupportInfoOut)
def forgot_password(payload: ForgotStartIn, request: Request, db: Session = Depends(get_db)):
    """Record the request and tell the user how to reach the admin.

    Nothing is sent and nothing is changed here. The reply is identical
    whether or not the username exists, so this cannot be used to discover
    who has an account.
    """
    user = db.scalar(select(User).where(User.username == normalize_username(payload.username)))
    if user is not None:
        auth_service.log_event(
            db, "reset", False, user=user, reason="user requested a reset", request=request
        )

    return SupportInfoOut(
        support_email=settings.SUPPORT_EMAIL,
        message=(
            f"Password resets are handled by the administrator. Email "
            f"{settings.SUPPORT_EMAIL} from an address you can be reached at, "
            "including your username, and you'll be sent a new password."
        ),
    )


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
