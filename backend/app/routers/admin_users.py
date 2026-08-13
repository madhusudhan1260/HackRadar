"""Admin-only portal: who registered, who logged in, and when.

Every route here depends on `require_admin`, so a normal account gets a 403
even if it knows the URL.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import require_admin
from ..models import AuthSession, Bookmark, LoginEvent, OtpCode, Profile, User
from ..schemas import (
    AdminOverviewOut,
    AdminResetPasswordIn,
    AdminUserOut,
    LoginEventOut,
    OtpLogOut,
)
from ..security import hash_password, mask_phone, password_problem
from ..services import auth as auth_service
from ..services.sms import provider_status

router = APIRouter(
    prefix="/api/admin", tags=["admin-portal"], dependencies=[Depends(require_admin)]
)


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@router.get("/overview", response_model=AdminOverviewOut)
def overview(db: Session = Depends(get_db)):
    users = db.scalars(select(User)).all()
    midnight = _naive_now().replace(hour=0, minute=0, second=0, microsecond=0)

    events_today = db.scalars(
        select(LoginEvent).where(
            LoginEvent.event == "login", LoginEvent.created_at >= midnight
        )
    ).all()

    return AdminOverviewOut(
        total_users=len(users),
        active_users=sum(1 for u in users if u.status == "active"),
        pending_users=sum(1 for u in users if u.status == "pending"),
        admins=sum(1 for u in users if u.role == "admin"),
        logins_today=sum(1 for e in events_today if e.success),
        failed_logins_today=sum(1 for e in events_today if not e.success),
        sms=provider_status(),
    )


@router.get("/users", response_model=list[AdminUserOut])
def list_users(
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="Search name, username or phone"),
    status_filter: str = Query("all", pattern="^(all|active|pending|blocked)$"),
    sort: str = Query("recent", pattern="^(recent|name|logins|last_login)$"),
):
    """Every registered account, with the full phone number."""
    stmt = select(User)
    if q:
        needle = f"%{q.strip().lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(User.name).like(needle),
                func.lower(User.username).like(needle),
                User.phone.like(needle),
            )
        )
    if status_filter != "all":
        stmt = stmt.where(User.status == status_filter)

    users = db.scalars(stmt).all()

    session_counts = dict(
        db.execute(
            select(AuthSession.user_id, func.count(AuthSession.id))
            .where(AuthSession.revoked_at.is_(None), AuthSession.expires_at > _naive_now())
            .group_by(AuthSession.user_id)
        ).all()
    )
    bookmark_counts = dict(
        db.execute(
            select(Profile.user_id, func.count(Bookmark.id))
            .join(Bookmark, Bookmark.profile_id == Profile.id)
            .group_by(Profile.user_id)
        ).all()
    )

    if sort == "name":
        users.sort(key=lambda u: u.name.lower())
    elif sort == "logins":
        users.sort(key=lambda u: -u.login_count)
    elif sort == "last_login":
        users.sort(key=lambda u: u.last_login_at or datetime.min, reverse=True)
    else:
        users.sort(key=lambda u: u.created_at, reverse=True)

    return [
        AdminUserOut(
            id=u.id,
            username=u.username,
            name=u.name,
            phone=u.phone,
            phone_masked=mask_phone(u.phone),
            role=u.role,
            status=u.status,
            phone_verified=u.phone_verified,
            created_at=u.created_at,
            last_login_at=u.last_login_at,
            login_count=u.login_count,
            active_sessions=session_counts.get(u.id, 0),
            bookmarks=bookmark_counts.get(u.id, 0),
        )
        for u in users
    ]


@router.get("/login-events", response_model=list[LoginEventOut])
def login_events(
    db: Session = Depends(get_db),
    limit: int = Query(100, ge=1, le=500),
    only_failed: bool = False,
    days: int = Query(30, ge=1, le=365),
):
    """Recent sign-in activity, joined to the account's name and phone."""
    since = _naive_now() - timedelta(days=days)
    stmt = select(LoginEvent).where(LoginEvent.created_at >= since)
    if only_failed:
        stmt = stmt.where(LoginEvent.success.is_(False))

    events = db.scalars(
        stmt.order_by(LoginEvent.created_at.desc()).limit(limit)
    ).all()

    user_ids = {e.user_id for e in events if e.user_id}
    users = {
        u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    } if user_ids else {}

    return [
        LoginEventOut(
            id=e.id,
            user_id=e.user_id,
            username_tried=e.username_tried,
            name=users[e.user_id].name if e.user_id in users else "",
            phone=users[e.user_id].phone if e.user_id in users else "",
            event=e.event,
            success=e.success,
            reason=e.reason,
            ip=e.ip,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.get("/otp-log", response_model=list[OtpLogOut])
def otp_log(db: Session = Depends(get_db), limit: int = Query(50, ge=1, le=200)):
    """Recent verification-code sends and whether delivery succeeded.

    Codes themselves are stored only as hashes and are never returned here.
    """
    codes = db.scalars(
        select(OtpCode).order_by(OtpCode.created_at.desc()).limit(limit)
    ).all()

    user_ids = {c.user_id for c in codes}
    users = {
        u.id: u for u in db.scalars(select(User).where(User.id.in_(user_ids))).all()
    } if user_ids else {}

    now = _naive_now()
    return [
        OtpLogOut(
            id=c.id,
            username=users[c.user_id].username if c.user_id in users else "",
            name=users[c.user_id].name if c.user_id in users else "",
            sent_to=c.sent_to,
            purpose=c.purpose,
            delivered=c.delivered,
            delivery_note=c.delivery_note,
            attempts=c.attempts,
            consumed=c.consumed_at is not None,
            expired=c.consumed_at is None and c.expires_at < now,
            created_at=c.created_at,
        )
        for c in codes
    ]


@router.post("/users/{user_id}/reset-password")
def reset_user_password(
    user_id: int,
    payload: AdminResetPasswordIn,
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Set a new password for a user who has emailed asking for help.

    Existing passwords cannot be read back — they are bcrypt hashes. This
    replaces the password and signs the account out everywhere, so the
    only person who knows the new one is whoever you hand it to.
    """
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")

    problem = password_problem(payload.new_password)
    if problem:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, problem)

    user.password_hash = hash_password(payload.new_password)
    user.failed_attempts = 0
    user.locked_until = None
    db.commit()

    revoked = auth_service.revoke_all_sessions(db, user.id)
    auth_service.log_event(
        db,
        "reset",
        True,
        user=user,
        reason=f"password set by admin {admin.username}",
    )

    return {
        "id": user.id,
        "username": user.username,
        "phone": user.phone,
        "sessions_revoked": revoked,
        "message": f"New password set for {user.username}. Send it to them privately.",
    }


@router.post("/users/{user_id}/status")
def set_user_status(
    user_id: int,
    new_status: str = Query(..., pattern="^(active|blocked)$"),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    """Block or unblock an account. Blocking also kills its live sessions."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "You cannot change your own status.")
    if user.role == "admin" and new_status == "blocked":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Admins cannot be blocked.")

    user.status = new_status
    db.commit()

    revoked = auth_service.revoke_all_sessions(db, user.id) if new_status == "blocked" else 0
    return {"id": user.id, "status": user.status, "sessions_revoked": revoked}


@router.delete("/users/{user_id}/sessions", status_code=200)
def force_signout(
    user_id: int, db: Session = Depends(get_db), admin: User = Depends(require_admin)
):
    """Sign an account out of every device."""
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such user.")
    return {"id": user.id, "sessions_revoked": auth_service.revoke_all_sessions(db, user.id)}
