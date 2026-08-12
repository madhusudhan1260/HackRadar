"""The ingestion pipeline: collect -> clean -> classify -> dedupe -> store.

This is the "DATA COLLECTOR / CLEAN / AI CLASSIFICATION" stage of the
architecture. Running it is idempotent: re-ingesting the same listing
updates the existing row instead of creating a duplicate.
"""
from __future__ import annotations

import logging
from dataclasses import asdict
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..collectors import RawHackathon, get_collector
from ..config import settings
from ..models import Hackathon, IngestRun
from . import normalize
from .classifier import classify, extract_tags

log = logging.getLogger(__name__)


def build_row_fields(raw: RawHackathon) -> dict:
    """Turn a RawHackathon into typed column values."""
    title = normalize.strip_html(raw.title)
    description = normalize.strip_html(raw.description)
    blob = f"{title} {description} {raw.location} {' '.join(raw.tags)}"

    deadline = normalize.parse_date(raw.deadline)
    start_date = normalize.parse_date(raw.start_date)
    end_date = normalize.parse_date(raw.end_date)
    # Some sources only give the event window; treat its end as the deadline.
    if deadline is None:
        deadline = end_date or start_date

    location = normalize.strip_html(raw.location)
    mode = normalize.parse_mode(raw.mode_hint, location, title, description)
    is_india = normalize.detect_india(location, raw.mode_hint, title, description)

    prize_inr = normalize.parse_prize_inr(raw.prize_text, raw.prize_currency)
    is_free, fee_inr = normalize.parse_fee(f"{raw.fee_text} {description}")
    team_min, team_max = normalize.parse_team_size(raw.team_text or description)

    categories = classify(title, description, raw.tags)
    tags = extract_tags(title, description, raw.tags)

    status = raw.status
    if deadline and deadline < date.today():
        status = "closed"

    return {
        "source": raw.source,
        "source_id": str(raw.source_id),
        "url": raw.url,
        "cluster_key": normalize.cluster_key(title),
        "title": title[:400],
        "description": description[:4000],
        "organizer": normalize.strip_html(raw.organizer)[:240],
        "image_url": raw.image_url[:600],
        "deadline": deadline,
        "start_date": start_date,
        "end_date": end_date,
        "mode": mode,
        "location": location[:240],
        "country": normalize.parse_country(location) or ("India" if is_india else ""),
        "is_india": is_india,
        "prize_text": normalize.strip_html(raw.prize_text)[:240],
        "prize_inr": prize_inr,
        "is_free": is_free,
        "fee_inr": fee_inr,
        "team_min": team_min,
        "team_max": team_max,
        "is_student_only": normalize.detect_student_only(title, description, blob),
        "categories": categories,
        "tags": tags,
        "status": status,
        "raw": _jsonable(raw.raw),
    }


def upsert(db: Session, fields: dict) -> str:
    """Insert or update one hackathon. Returns 'created' or 'updated'."""
    existing = db.scalar(
        select(Hackathon).where(
            Hackathon.source == fields["source"],
            Hackathon.source_id == fields["source_id"],
        )
    )
    if existing is None:
        db.add(Hackathon(**fields))
        return "created"

    for key, value in fields.items():
        if key != "first_seen_at":
            setattr(existing, key, value)
    return "updated"


def run_collector(db: Session, name: str, limit: int = 200) -> dict:
    """Run one collector end-to-end and record the outcome."""
    run = IngestRun(source=name)
    db.add(run)
    db.commit()

    created = updated = fetched = 0
    try:
        records = get_collector(name).fetch(limit=limit)
        fetched = len(records)
        for record in records:
            try:
                result = upsert(db, build_row_fields(record))
                created += result == "created"
                updated += result == "updated"
            except Exception:
                log.exception("Failed to store %s record %s", name, record.source_id)
                db.rollback()
        db.commit()
        run.ok = True
    except Exception as exc:
        log.exception("Collector %s failed", name)
        db.rollback()
        run.ok = False
        run.error = f"{type(exc).__name__}: {exc}"[:2000]

    run.fetched, run.created, run.updated = fetched, created, updated
    run.finished_at = datetime.now(timezone.utc)
    db.add(run)
    db.commit()

    return {
        "source": name,
        "ok": run.ok,
        "fetched": fetched,
        "created": created,
        "updated": updated,
        "error": run.error,
    }


def run_all(db: Session, sources: list[str] | None = None, limit: int = 200) -> list[dict]:
    names = sources or settings.ENABLED_COLLECTORS
    return [run_collector(db, name, limit=limit) for name in names]


def close_expired(db: Session) -> int:
    """Mark past-deadline listings as closed so filters stay honest."""
    rows = db.scalars(
        select(Hackathon).where(
            Hackathon.status == "open", Hackathon.deadline.is_not(None)
        )
    ).all()
    changed = 0
    today = date.today()
    for row in rows:
        if row.deadline and row.deadline < today:
            row.status = "closed"
            changed += 1
    db.commit()
    return changed


def _jsonable(value):
    """Strip anything the JSON column cannot store."""
    try:
        import json

        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return {"_note": "raw payload omitted (not JSON serialisable)"}


__all__ = ["build_row_fields", "upsert", "run_collector", "run_all", "close_expired", "asdict"]
