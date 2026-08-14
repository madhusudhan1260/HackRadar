"""Internship browsing, bookmarks, and ingestion — mirrors routers/hackathons.py
and routers/admin.py's shape, scoped to the Internship table."""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from ..db import SessionLocal, get_db
from ..deps import get_current_profile, get_current_user
from ..internship_collectors import available as available_collectors
from ..models import Internship, InternshipBookmark, InternshipIngestRun, Profile
from ..schemas import (
    InternshipIngestResult,
    InternshipList,
    InternshipOut,
    InternshipStatsOut,
    IngestRequest,
    SourceInfo,
)
from ..services import internship_pipeline
from ..services.internship_matcher import format_inr, score

router = APIRouter(prefix="/api/internships", tags=["internships"])


def _to_out(row: Internship, profile: Profile, bookmarked_ids: set[int], today: date) -> InternshipOut:
    out = InternshipOut.model_validate(row)
    out.days_left = (row.deadline - today).days if row.deadline else None
    out.stipend_display = format_inr(row.stipend_inr) if row.stipend_inr else "—"
    out.bookmarked = row.id in bookmarked_ids
    out.match = score(row, profile)
    return out


@router.get("", response_model=InternshipList)
def list_internships(
    db: Session = Depends(get_db),
    q: str | None = None,
    region: str = Query("all", pattern="^(all|india|global)$"),
    category: list[str] | None = Query(None),
    mode: str = Query("all", pattern="^(all|remote|onsite|hybrid)$"),
    paid_only: bool = False,
    status: str = Query("open", pattern="^(open|closed|all)$"),
    bookmarked_only: bool = False,
    sort: str = Query("match", pattern="^(match|recent|deadline|stipend|title)$"),
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
    profile: Profile = Depends(get_current_profile),
):
    today = date.today()
    stmt = select(Internship)

    if status != "all":
        stmt = stmt.where(Internship.status == status)
    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Internship.title).like(needle),
                func.lower(Internship.company).like(needle),
                func.lower(Internship.description).like(needle),
                func.lower(func.cast(Internship.tags, String)).like(needle),
            )
        )
    if region == "india":
        stmt = stmt.where(Internship.is_india.is_(True))
    elif region == "global":
        stmt = stmt.where(Internship.is_india.is_(False))
    if mode != "all":
        stmt = stmt.where(Internship.mode == mode)
    if paid_only:
        stmt = stmt.where(Internship.is_paid.is_(True))

    bookmarked_ids = {
        b.internship_id
        for b in db.scalars(
            select(InternshipBookmark).where(InternshipBookmark.profile_id == profile.id)
        ).all()
    }
    if bookmarked_only:
        if not bookmarked_ids:
            return InternshipList(total=0, page=page, per_page=per_page, items=[])
        stmt = stmt.where(Internship.id.in_(bookmarked_ids))

    rows = db.scalars(stmt).all()
    if category:
        wanted = {c.lower() for c in category}
        rows = [r for r in rows if wanted & {c.lower() for c in (r.categories or [])}]

    far_future = date(2999, 1, 1)
    if sort == "recent":
        rows = sorted(rows, key=lambda r: r.first_seen_at, reverse=True)
    elif sort == "deadline":
        rows = sorted(rows, key=lambda r: r.deadline or far_future)
    elif sort == "stipend":
        rows = sorted(rows, key=lambda r: -r.stipend_inr)
    elif sort == "title":
        rows = sorted(rows, key=lambda r: r.title.lower())
    else:  # match
        rows = sorted(rows, key=lambda r: -score(r, profile)["score"])

    total = len(rows)
    window = rows[(page - 1) * per_page : (page - 1) * per_page + per_page]
    items = [_to_out(r, profile, bookmarked_ids, today) for r in window]
    return InternshipList(total=total, page=page, per_page=per_page, items=items)


@router.get("/stats", response_model=InternshipStatsOut)
def stats(db: Session = Depends(get_db)):
    rows = db.scalars(select(Internship)).all()
    open_rows = [r for r in rows if r.status == "open"]

    by_source: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for row in rows:
        by_source[row.source] = by_source.get(row.source, 0) + 1
        for cat in row.categories or []:
            by_category[cat] = by_category.get(cat, 0) + 1

    last_run = db.scalar(
        select(InternshipIngestRun).order_by(InternshipIngestRun.started_at.desc()).limit(1)
    )
    return InternshipStatsOut(
        total=len(rows),
        open=len(open_rows),
        india=sum(1 for r in open_rows if r.is_india),
        remote=sum(1 for r in open_rows if r.mode in ("remote", "hybrid")),
        paid=sum(1 for r in open_rows if r.is_paid),
        by_source=dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        by_category=dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        last_ingest=last_run.finished_at if last_run else None,
    )


@router.get("/sources", response_model=list[SourceInfo], dependencies=[Depends(get_current_user)])
def list_sources(db: Session = Depends(get_db)):
    from ..config import settings

    counts = dict(
        db.execute(
            select(Internship.source, func.count(Internship.id)).group_by(Internship.source)
        ).all()
    )
    infos = []
    for entry in available_collectors():
        last = db.scalar(
            select(InternshipIngestRun)
            .where(InternshipIngestRun.source == entry["name"])
            .order_by(InternshipIngestRun.started_at.desc())
            .limit(1)
        )
        infos.append(
            SourceInfo(
                name=entry["name"],
                access_note=entry["access_note"],
                enabled=entry["name"] in settings.ENABLED_INTERNSHIP_COLLECTORS,
                last_run=last.finished_at if last else None,
                last_ok=last.ok if last else None,
                count=counts.get(entry["name"], 0),
            )
        )
    return infos


@router.post("/ingest", response_model=list[InternshipIngestResult], dependencies=[Depends(get_current_user)])
def ingest(payload: IngestRequest, db: Session = Depends(get_db)):
    results = internship_pipeline.run_all(db, sources=payload.sources, limit=payload.limit)
    internship_pipeline.close_expired(db)
    return results


@router.get("/{internship_id}", response_model=InternshipOut)
def get_internship(
    internship_id: int, db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)
):
    row = db.get(Internship, internship_id)
    if row is None:
        raise HTTPException(404, "Internship not found")
    bookmarked_ids = {
        b.internship_id
        for b in db.scalars(
            select(InternshipBookmark).where(InternshipBookmark.profile_id == profile.id)
        ).all()
    }
    return _to_out(row, profile, bookmarked_ids, date.today())


@router.post("/{internship_id}/bookmark", response_model=InternshipOut, status_code=201)
def add_bookmark(internship_id: int, db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)):
    row = db.get(Internship, internship_id)
    if row is None:
        raise HTTPException(404, "Internship not found")
    existing = db.scalar(
        select(InternshipBookmark).where(
            InternshipBookmark.profile_id == profile.id,
            InternshipBookmark.internship_id == internship_id,
        )
    )
    if existing is None:
        db.add(InternshipBookmark(profile_id=profile.id, internship_id=internship_id))
        db.commit()
    return _to_out(row, profile, {row.id}, date.today())


@router.delete("/{internship_id}/bookmark", status_code=204)
def remove_bookmark(internship_id: int, db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)):
    existing = db.scalar(
        select(InternshipBookmark).where(
            InternshipBookmark.profile_id == profile.id,
            InternshipBookmark.internship_id == internship_id,
        )
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
