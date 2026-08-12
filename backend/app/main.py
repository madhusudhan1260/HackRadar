"""HackRadar API — one place for every hackathon."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from apscheduler.schedulers.background import BackgroundScheduler
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import func, select

from .config import settings
from .db import SessionLocal, init_db
from .models import Hackathon
from .routers import admin, hackathons, profile
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


def _bootstrap_if_empty() -> None:
    """First run with an empty table: load the offline seed set immediately."""
    db = SessionLocal()
    try:
        count = db.scalar(select(func.count(Hackathon.id))) or 0
        if count == 0:
            log.info("Empty database — loading seed data")
            pipeline.run_collector(db, "seed")
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    global scheduler
    init_db()
    _bootstrap_if_empty()

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

app.include_router(hackathons.router)
app.include_router(profile.router)
app.include_router(admin.router)


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
