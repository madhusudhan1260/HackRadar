"""HackRadar API — one place for every hackathon."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from .config import settings
from .db import SessionLocal, init_db
from .models import Hackathon
from .routers import admin, admin_users, auth, hackathons, profile
from .services import pipeline

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)
log = logging.getLogger("hackradar")

scheduler: BackgroundScheduler | None = None


def _scheduled_ingest() -> None:
    db = SessionLocal()
    try:
        log.info("Scheduled ingest starting")
        results = pipeline.run_all(db)
        pipeline.close_expired(db)
        for r in results:
            log.info(
                "  %s: fetched=%s created=%s updated=%s ok=%s",
                r["source"], r["fetched"], r["created"], r["updated"], r["ok"],
            )
    finally:
        db.close()


def _report_email_transport() -> None:
    """Say plainly how verification codes will be delivered.

    A misconfigured transport is otherwise invisible until a user tries to
    register and the send fails.
    """
    from .services.mailer import provider_status

    status = provider_status()
    if status["is_live"]:
        log.info("Verification codes: %s", status["note"])
    elif status["provider"] == "console":
        log.warning(
            "Verification codes are NOT being emailed — running in console mode. "
            "Set BREVO_API_KEY and EMAIL_FROM to send for real."
        )
    else:
        log.error(
            "Email transport %r is selected but incompletely configured. "
            "Registration will fail until it is fixed.",
            status["provider"],
        )


def _bootstrap_admin() -> None:
    """Create the first admin from environment variables.

    Exists because hosts commonly put shell access behind a paid plan,
    leaving no way to run `manage.py create-admin` on the live database.

    Only ever fires when there is no admin at all, so it cannot be used to
    change an existing account's password or quietly add a second admin.
    """
    from .models import User
    from .security import (
        hash_password,
        normalize_phone,
        normalize_username,
        password_problem,
        phone_problem,
        username_problem,
    )
    from .services.auth import ensure_profile

    username = normalize_username(settings.ADMIN_USERNAME)
    password = settings.ADMIN_PASSWORD
    if not (username and password):
        return

    db = SessionLocal()
    try:
        if db.scalar(select(User).where(User.role == "admin")) is not None:
            log.info(
                "ADMIN_USERNAME is set but an admin already exists — ignoring. "
                "Remove ADMIN_PASSWORD from the environment."
            )
            return

        phone = normalize_phone(settings.ADMIN_PHONE)
        for problem in (username_problem(username), phone_problem(phone), password_problem(password)):
            if problem:
                log.error("Cannot bootstrap admin: %s", problem)
                return

        if db.scalar(select(User).where(User.username == username)) is not None:
            log.error("Cannot bootstrap admin: username %r is already taken.", username)
            return
        if db.scalar(select(User).where(User.phone == phone)) is not None:
            log.error("Cannot bootstrap admin: phone %s is already registered.", phone)
            return

        admin = User(
            username=username,
            name=(settings.ADMIN_NAME or "Administrator").strip(),
            phone=phone,
            password_hash=hash_password(password),
            role="admin",
            status="active",
            phone_verified=True,
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
        ensure_profile(db, admin)

        log.warning(
            "Created admin %r from environment variables. "
            "DELETE ADMIN_PASSWORD from the environment now — it is not needed "
            "again and should not sit in your dashboard.",
            username,
        )
    finally:
        db.close()


def _check_admin_integrity() -> None:
    """The app is single-admin by design. Shout if that ever stops being true.

    Registration can only ever create role='user', so more than one admin
    means someone edited the database directly — worth knowing about.
    """
    from .models import User

    db = SessionLocal()
    try:
        admins = db.scalars(select(User).where(User.role == "admin")).all()
        if not admins:
            log.warning(
                "No admin account exists. Create one with: "
                "python scripts/manage.py create-admin"
            )
        elif len(admins) > 1:
            log.error(
                "SECURITY: %s accounts hold the admin role (%s). Expected exactly "
                "one. Demote the extras with create-admin --replace.",
                len(admins),
                ", ".join(a.username for a in admins),
            )
        else:
            log.info("Admin account: %s", admins[0].username)
    finally:
        db.close()


def _bootstrap_if_empty() -> None:
    """First run with an empty table: pull real listings in the background.

    Deliberately does NOT load the bundled sample data — those rows link to
    example.com, which is fine for tests but looks broken to a real visitor.
    """
    db = SessionLocal()
    try:
        count = db.scalar(select(func.count(Hackathon.id))) or 0
    finally:
        db.close()

    if count:
        return

    log.info("Empty database — fetching real listings in the background")
    threading.Thread(target=_scheduled_ingest, daemon=True).start()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    init_db()
    _bootstrap_if_empty()
    _bootstrap_admin()
    _check_admin_integrity()
    _report_email_transport()

    if settings.RUN_SCHEDULER:
        scheduler = BackgroundScheduler(daemon=True)
        scheduler.add_job(
            _scheduled_ingest,
            "interval",
            minutes=settings.INGEST_INTERVAL_MINUTES,
            id="ingest",
        )
        scheduler.start()
        log.info(
            "Scheduler on — ingesting %s every %s min",
            ", ".join(settings.ENABLED_COLLECTORS),
            settings.INGEST_INTERVAL_MINUTES,
        )

    yield

    if scheduler is not None:
        scheduler.shutdown(wait=False)


app = FastAPI(
    title="HackRadar API",
    description="Aggregates hackathons from multiple platforms into one dashboard.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(hackathons.router)
app.include_router(profile.router)
app.include_router(admin.router)
app.include_router(admin_users.router)


@app.get("/api/health", tags=["meta"])
def health():
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(Hackathon.id))) or 0
    finally:
        db.close()
    return {
        "status": "ok",
        "hackathons": total,
        "collectors": settings.ENABLED_COLLECTORS,
        "scheduler": settings.RUN_SCHEDULER,
        "llm_enrichment": bool(settings.ANTHROPIC_API_KEY),
    }
