"""Ingestion control and notification endpoints."""
from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..collectors import available
from ..config import settings
from ..db import SessionLocal, get_db
from ..deps import get_current_profile, get_current_user
from ..models import Hackathon, IngestRun, Profile
from ..schemas import IngestRequest, IngestResult, SourceInfo
from ..services import pipeline
from ..services.notifier import dispatch, pending_alerts

router = APIRouter(
    prefix="/api", tags=["admin"], dependencies=[Depends(get_current_user)]
)


@router.get("/sources", response_model=list[SourceInfo])
def list_sources(db: Session = Depends(get_db)):
    counts = dict(
        db.execute(
            select(Hackathon.source, func.count(Hackathon.id)).group_by(Hackathon.source)
        ).all()
    )
    infos = []
    for entry in available():
        last = db.scalar(
            select(IngestRun)
            .where(IngestRun.source == entry["name"])
            .order_by(IngestRun.started_at.desc())
            .limit(1)
        )
        infos.append(
            SourceInfo(
                name=entry["name"],
                access_note=entry["access_note"],
                enabled=entry["name"] in settings.ENABLED_COLLECTORS,
                last_run=last.finished_at if last else None,
                last_ok=last.ok if last else None,
                count=counts.get(entry["name"], 0),
            )
        )
    return infos


@router.post("/ingest", response_model=list[IngestResult])
def ingest(payload: IngestRequest, db: Session = Depends(get_db)):
    """Run collectors synchronously and return what changed."""
    results = pipeline.run_all(db, sources=payload.sources, limit=payload.limit)
    pipeline.close_expired(db)
    return results


@router.post("/ingest/async", status_code=202)
def ingest_async(payload: IngestRequest, background: BackgroundTasks):
    """Kick off ingestion without blocking the request."""

    def _run() -> None:
        db = SessionLocal()
        try:
            pipeline.run_all(db, sources=payload.sources, limit=payload.limit)
            pipeline.close_expired(db)
        finally:
            db.close()

    background.add_task(_run)
    return {"status": "started", "sources": payload.sources or settings.ENABLED_COLLECTORS}


@router.get("/ingest/runs")
def ingest_runs(db: Session = Depends(get_db), limit: int = 20):
    runs = db.scalars(
        select(IngestRun).order_by(IngestRun.started_at.desc()).limit(limit)
    ).all()
    return [
        {
            "id": r.id,
            "source": r.source,
            "started_at": r.started_at,
            "finished_at": r.finished_at,
            "fetched": r.fetched,
            "created": r.created,
            "updated": r.updated,
            "ok": r.ok,
            "error": r.error,
        }
        for r in runs
    ]


@router.get("/notifications/preview")
def preview_notifications(
    db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)
):
    """What would be sent right now, without sending anything."""
    from ..services import mailer
    from ..services.notifier import _destination_email, pending_internship_alerts

    alerts = pending_alerts(db, profile) + pending_internship_alerts(db, profile)
    alerts.sort(key=lambda a: (a["days_left"], -a["match"]["score"]))
    return {
        "count": len(alerts),
        "email_configured": mailer.is_configured() and bool(_destination_email(db, profile)),
        "telegram_configured": bool(
            settings.TELEGRAM_BOT_TOKEN and (profile.telegram_chat_id or settings.TELEGRAM_CHAT_ID)
        ),
        "alerts": [
            {
                "id": a["row"].id,
                "type": a["type"],
                "title": a["row"].title,
                "deadline": a["row"].deadline,
                "days_left": a["days_left"],
                "match_score": a["match"]["score"],
                "bookmarked": a["bookmarked"],
            }
            for a in alerts
        ],
    }


@router.post("/notifications/send")
def send_notifications(
    db: Session = Depends(get_db),
    dry_run: bool = False,
    profile: Profile = Depends(get_current_profile),
):
    return dispatch(db, profile, dry_run=dry_run)
