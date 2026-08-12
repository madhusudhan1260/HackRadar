"""Profile, bookmarks and AI recommendations.

Each account owns exactly one profile, so bookmarks and match scores are
per-user. The profile is resolved from the bearer token by
`deps.get_current_profile`.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_profile
from ..models import Bookmark, Hackathon, Profile
from ..schemas import BookmarkIn, HackathonOut, ProfileIn, ProfileOut
from ..serializers import to_out
from ..services.dedupe import collapse
from ..services.matcher import score

router = APIRouter(prefix="/api", tags=["profile"])

DEFAULT_SKILLS = ["Python", "C++", "JavaScript", "HTML/CSS", "Flask", "Machine Learning"]
DEFAULT_INTERESTS = ["ai-ml", "web", "cybersecurity", "cloud"]


def _score_cache(row: Hackathon, profile: Profile, today: date) -> int:
    """Score used for sorting. Cheap enough to call per row."""
    return score(row, profile, today=today)["score"]


# --------------------------------------------------------------------------
# Profile
# --------------------------------------------------------------------------


@router.get("/profile", response_model=ProfileOut)
def read_profile(profile: Profile = Depends(get_current_profile)):
    return profile


@router.put("/profile", response_model=ProfileOut)
def update_profile(
    payload: ProfileIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        if value is not None:
            setattr(profile, field, value)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


# --------------------------------------------------------------------------
# Recommendations
# --------------------------------------------------------------------------


@router.get("/recommendations", response_model=list[HackathonOut])
def recommendations(
    db: Session = Depends(get_db),
    limit: int = Query(12, ge=1, le=50),
    min_score: int = Query(40, ge=0, le=100),
    profile: Profile = Depends(get_current_profile),
):
    """Best-matching open hackathons for the current profile."""
    today = date.today()

    rows = db.scalars(
        select(Hackathon).where(Hackathon.status == "open")
    ).all()
    bookmarked_ids = {
        b.hackathon_id
        for b in db.scalars(select(Bookmark).where(Bookmark.profile_id == profile.id)).all()
    }

    scored = []
    for row, mirrors in collapse(rows):
        item = to_out(row, profile=profile, bookmarked_ids=bookmarked_ids, mirrors=mirrors, today=today)
        if item.match and item.match.score >= min_score:
            scored.append(item)

    scored.sort(
        key=lambda i: (-(i.match.score if i.match else 0), i.days_left if i.days_left is not None else 999)
    )
    return scored[:limit]


# --------------------------------------------------------------------------
# Bookmarks
# --------------------------------------------------------------------------


@router.get("/bookmarks", response_model=list[HackathonOut])
def list_bookmarks(
    db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)
):
    today = date.today()
    bookmarks = db.scalars(
        select(Bookmark).where(Bookmark.profile_id == profile.id)
    ).all()
    ids = {b.hackathon_id for b in bookmarks}
    if not ids:
        return []

    rows = db.scalars(select(Hackathon).where(Hackathon.id.in_(ids))).all()
    items = [to_out(r, profile=profile, bookmarked_ids=ids, today=today) for r in rows]
    items.sort(key=lambda i: i.days_left if i.days_left is not None else 999)
    return items


@router.post("/bookmarks", response_model=HackathonOut, status_code=201)
def add_bookmark(
    payload: BookmarkIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
):
    row = db.get(Hackathon, payload.hackathon_id)
    if row is None:
        raise HTTPException(404, "Hackathon not found")

    existing = db.scalar(
        select(Bookmark).where(
            Bookmark.profile_id == profile.id,
            Bookmark.hackathon_id == payload.hackathon_id,
        )
    )
    if existing is None:
        db.add(
            Bookmark(
                profile_id=profile.id,
                hackathon_id=payload.hackathon_id,
                note=payload.note,
            )
        )
        db.commit()
    elif payload.note:
        existing.note = payload.note
        db.commit()

    return to_out(row, profile=profile, bookmarked_ids={row.id})


@router.delete("/bookmarks/{hackathon_id}", status_code=204)
def remove_bookmark(
    hackathon_id: int,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
):
    existing = db.scalar(
        select(Bookmark).where(
            Bookmark.profile_id == profile.id,
            Bookmark.hackathon_id == hackathon_id,
        )
    )
    if existing is not None:
        db.delete(existing)
        db.commit()
