"""Internship ingestion: collect -> clean -> classify -> store.

The internship equivalent of services/pipeline.py. Deliberately reuses
normalize.py and classifier.py as-is — both were already written generically
enough (they operate on title/description/location strings, nothing
hackathon-specific) that internships needed no forked copies of them.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..internship_collectors import RawInternship, get_collector
from ..models import Internship, InternshipIngestRun
from . import normalize
from .classifier import classify, extract_tags

log = logging.getLogger(__name__)


def build_row_fields(raw: RawInternship) -> dict:
    title = normalize.strip_html(raw.title)
    description = normalize.strip_html(raw.description)

    deadline = normalize.parse_date(raw.deadline)
    posted_date = normalize.parse_date(raw.posted_date)

    location = normalize.strip_html(raw.location)
    # parse_mode speaks the hackathon vocabulary (online/offline/hybrid);
    # internships use the vocabulary job seekers actually expect
    # (remote/onsite/hybrid) — translated here rather than at every caller.
    _MODE_MAP = {"online": "remote", "offline": "onsite", "hybrid": "hybrid"}
    mode = _MODE_MAP[normalize.parse_mode(raw.mode_hint, location, title, description)]
    is_india = normalize.detect_india(location, raw.mode_hint, title, description)

    stipend_inr = normalize.parse_prize_inr(raw.stipend_text, raw.stipend_currency)
    # parse_fee exists for hackathon entry fees — the opposite question
    # (would *you* pay), so it is not reused here. A stipend amount that
    # actually parsed means paid; an explicit "unpaid" mention means not;
    # absent either, whether it pays is simply unknown, so it defaults to
    # paid rather than asserting "unpaid" with no evidence for it.
    unpaid_mentioned = "unpaid" in f"{raw.stipend_text} {description}".lower()
    is_paid = bool(stipend_inr) or not unpaid_mentioned

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
        "company": normalize.strip_html(raw.company)[:240],
        "company_url": raw.company_url[:400],
        "description": description[:4000],
        "deadline": deadline,
        "posted_date": posted_date,
        "term": raw.term[:80],
        "mode": mode,
        "location": location[:240],
        "country": normalize.parse_country(location) or ("India" if is_india else ""),
        "is_india": is_india,
        "stipend_text": normalize.strip_html(raw.stipend_text)[:240],
        "stipend_inr": stipend_inr,
        "is_paid": is_paid,
        "duration_text": raw.duration_text[:120],
        "eligibility": raw.eligibility[:240],
        "categories": categories,
        "tags": tags,
        "status": status,
        "raw": _jsonable(raw.raw),
    }


def upsert(db: Session, fields: dict) -> str:
    existing = db.scalar(
        select(Internship).where(
            Internship.source == fields["source"],
            Internship.source_id == fields["source_id"],
        )
    )
    if existing is None:
        db.add(Internship(**fields))
        return "created"

    for key, value in fields.items():
        if key != "first_seen_at":
            setattr(existing, key, value)
    return "updated"


def run_collector(db: Session, name: str, limit: int = 300) -> dict:
    run = InternshipIngestRun(source=name)
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
                log.exception("Failed to store internship %s record %s", name, record.source_id)
                db.rollback()
        db.commit()
        run.ok = True
    except Exception as exc:
        log.exception("Internship collector %s failed", name)
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


def run_all(db: Session, sources: list[str] | None = None, limit: int = 300) -> list[dict]:
    from ..config import settings

    names = sources or settings.ENABLED_INTERNSHIP_COLLECTORS
    return [run_collector(db, name, limit=limit) for name in names]


def close_expired(db: Session) -> int:
    rows = db.scalars(
        select(Internship).where(
            Internship.status == "open", Internship.deadline.is_not(None)
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
    try:
        import json

        json.dumps(value)
        return value
    except (TypeError, ValueError):
        return {"_note": "raw payload omitted (not JSON serialisable)"}
