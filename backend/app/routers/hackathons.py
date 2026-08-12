"""Hackathon browsing: filtered list, detail, deadline board, stats."""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import String, func, or_, select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Bookmark, Hackathon, IngestRun
from ..schemas import (
    DeadlineBoard,
    DeadlineGroup,
    HackathonList,
    HackathonOut,
    StatsOut,
)
from ..serializers import to_out
from ..services.dedupe import collapse
from .profile import current_profile

router = APIRouter(prefix="/api/hackathons", tags=["hackathons"])

# Prize buckets, in INR. Keys are what the frontend sends.
PRIZE_BUCKETS: dict[str, tuple[int, int | None]] = {
    "0-10k": (0, 10_000),
    "10k-1l": (10_000, 100_000),
    "1l+": (100_000, None),
}


@router.get("", response_model=HackathonList)
def list_hackathons(
    db: Session = Depends(get_db),
    q: str | None = Query(None, description="Free text search over title/description/tags"),
    region: str = Query("all", pattern="^(all|india|global)$"),
    category: list[str] | None = Query(None, description="Repeatable, e.g. category=ai-ml&category=web"),
    mode: str = Query("all", pattern="^(all|online|offline|hybrid)$"),
    prize: str | None = Query(None, description="One of 0-10k, 10k-1l, 1l+"),
    free_only: bool = False,
    student_only: bool = False,
    team_size: int | None = Query(None, ge=1, le=20),
    within_days: int | None = Query(None, ge=0, le=365),
    status: str = Query("open", pattern="^(open|closed|all)$"),
    bookmarked_only: bool = False,
    sort: str = Query("deadline", pattern="^(deadline|prize|match|recent|title)$"),
    group_duplicates: bool = True,
    page: int = Query(1, ge=1),
    per_page: int = Query(24, ge=1, le=100),
):
    """The main dashboard query. Every filter from the feature table lives here."""
    profile = current_profile(db)
    today = date.today()

    stmt = select(Hackathon)

    if status != "all":
        stmt = stmt.where(Hackathon.status == status)

    if q:
        needle = f"%{q.lower()}%"
        stmt = stmt.where(
            or_(
                func.lower(Hackathon.title).like(needle),
                func.lower(Hackathon.description).like(needle),
                func.lower(Hackathon.organizer).like(needle),
                func.lower(func.cast(Hackathon.tags, String)).like(needle),
            )
        )

    if region == "india":
        stmt = stmt.where(Hackathon.is_india.is_(True))
    elif region == "global":
        stmt = stmt.where(Hackathon.is_india.is_(False))

    if mode != "all":
        stmt = stmt.where(Hackathon.mode == mode)

    if prize:
        if prize not in PRIZE_BUCKETS:
            raise HTTPException(400, f"Unknown prize bucket {prize!r}")
        low, high = PRIZE_BUCKETS[prize]
        stmt = stmt.where(Hackathon.prize_inr >= low)
        if high is not None:
            stmt = stmt.where(Hackathon.prize_inr < high)

    if free_only:
        stmt = stmt.where(Hackathon.is_free.is_(True))
    if student_only:
        stmt = stmt.where(Hackathon.is_student_only.is_(True))

    if team_size:
        stmt = stmt.where(
            Hackathon.team_min <= team_size, Hackathon.team_max >= team_size
        )

    if within_days is not None:
        stmt = stmt.where(
            Hackathon.deadline.is_not(None),
            Hackathon.deadline >= today,
            Hackathon.deadline <= today + timedelta(days=within_days),
        )

    bookmarked_ids = {
        b.hackathon_id
        for b in db.scalars(select(Bookmark).where(Bookmark.profile_id == profile.id)).all()
    }
    if bookmarked_only:
        if not bookmarked_ids:
            return HackathonList(total=0, page=page, per_page=per_page, items=[])
        stmt = stmt.where(Hackathon.id.in_(bookmarked_ids))

    # Category filter lives in a JSON column, so it is applied in Python.
    rows = db.scalars(stmt).all()
    if category:
        wanted = {c.lower() for c in category}
        rows = [r for r in rows if wanted & {c.lower() for c in (r.categories or [])}]

    # --- de-duplicate across platforms ---------------------------------
    if group_duplicates:
        grouped = collapse(rows)
    else:
        grouped = [(r, []) for r in rows]

    # --- sort ------------------------------------------------------------
    far_future = date(2999, 1, 1)
    if sort == "deadline":
        grouped.sort(key=lambda g: (g[0].deadline or far_future, -g[0].prize_inr))
    elif sort == "prize":
        grouped.sort(key=lambda g: -g[0].prize_inr)
    elif sort == "recent":
        grouped.sort(key=lambda g: g[0].first_seen_at, reverse=True)
    elif sort == "title":
        grouped.sort(key=lambda g: g[0].title.lower())
    elif sort == "match":
        from .profile import _score_cache  # local import keeps module load light

        grouped.sort(
            key=lambda g: (-_score_cache(g[0], profile, today), g[0].deadline or far_future)
        )

    total = len(grouped)
    start = (page - 1) * per_page
    window = grouped[start : start + per_page]

    items = [
        to_out(row, profile=profile, bookmarked_ids=bookmarked_ids, mirrors=mirrors, today=today)
        for row, mirrors in window
    ]
    return HackathonList(total=total, page=page, per_page=per_page, items=items)


@router.get("/deadlines", response_model=DeadlineBoard)
def deadline_board(
    db: Session = Depends(get_db),
    bookmarked_only: bool = False,
    min_score: int = Query(0, ge=0, le=100),
    horizon_days: int = Query(30, ge=1, le=180),
):
    """The 'MY HACKATHONS / DEADLINES' board, bucketed by urgency."""
    profile = current_profile(db)
    today = date.today()
    limit_date = today + timedelta(days=horizon_days)

    rows = db.scalars(
        select(Hackathon).where(
            Hackathon.status == "open",
            Hackathon.deadline.is_not(None),
            Hackathon.deadline >= today,
            Hackathon.deadline <= limit_date,
        )
    ).all()

    bookmarked_ids = {
        b.hackathon_id
        for b in db.scalars(select(Bookmark).where(Bookmark.profile_id == profile.id)).all()
    }
    if bookmarked_only:
        rows = [r for r in rows if r.id in bookmarked_ids]

    buckets: dict[str, list] = {
        "Today": [],
        "This Week": [],
        "Next Week": [],
        "Later This Month": [],
    }

    for row, mirrors in collapse(rows):
        item = to_out(row, profile=profile, bookmarked_ids=bookmarked_ids, mirrors=mirrors, today=today)
        if item.match and item.match.score < min_score and row.id not in bookmarked_ids:
            continue
        days = item.days_left or 0
        if days <= 0:
            buckets["Today"].append(item)
        elif days <= 7:
            buckets["This Week"].append(item)
        elif days <= 14:
            buckets["Next Week"].append(item)
        else:
            buckets["Later This Month"].append(item)

    for items in buckets.values():
        items.sort(key=lambda i: (i.days_left or 0, -(i.match.score if i.match else 0)))

    return DeadlineBoard(
        groups=[DeadlineGroup(label=label, items=items) for label, items in buckets.items() if items],
        generated_on=today,
    )


@router.get("/stats", response_model=StatsOut)
def stats(db: Session = Depends(get_db)):
    today = date.today()
    rows = db.scalars(select(Hackathon)).all()

    by_source: dict[str, int] = {}
    by_category: dict[str, int] = {}
    for row in rows:
        by_source[row.source] = by_source.get(row.source, 0) + 1
        for cat in row.categories or []:
            by_category[cat] = by_category.get(cat, 0) + 1

    open_rows = [r for r in rows if r.status == "open"]
    last_run = db.scalar(
        select(IngestRun).order_by(IngestRun.started_at.desc()).limit(1)
    )

    return StatsOut(
        total=len(rows),
        open=len(open_rows),
        india=sum(1 for r in open_rows if r.is_india),
        online=sum(1 for r in open_rows if r.mode in ("online", "hybrid")),
        free=sum(1 for r in open_rows if r.is_free),
        student=sum(1 for r in open_rows if r.is_student_only),
        by_source=dict(sorted(by_source.items(), key=lambda kv: -kv[1])),
        by_category=dict(sorted(by_category.items(), key=lambda kv: -kv[1])),
        closing_this_week=sum(
            1
            for r in open_rows
            if r.deadline and today <= r.deadline <= today + timedelta(days=7)
        ),
        last_ingest=last_run.finished_at if last_run else None,
    )


@router.get("/{hackathon_id}", response_model=HackathonOut)
def get_hackathon(hackathon_id: int, db: Session = Depends(get_db)):
    row = db.get(Hackathon, hackathon_id)
    if row is None:
        raise HTTPException(404, "Hackathon not found")

    profile = current_profile(db)
    bookmarked_ids = {
        b.hackathon_id
        for b in db.scalars(select(Bookmark).where(Bookmark.profile_id == profile.id)).all()
    }
    mirrors = [
        {"source": m.source, "url": m.url}
        for m in db.scalars(
            select(Hackathon).where(
                Hackathon.cluster_key == row.cluster_key, Hackathon.id != row.id
            )
        ).all()
        if row.cluster_key
    ]
    return to_out(row, profile=profile, bookmarked_ids=bookmarked_ids, mirrors=mirrors)
