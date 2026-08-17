"""Application tracker.

Everything you've bookmarked, hackathon or internship, with a status you
control — saved -> applied -> interviewing -> rejected/accepted. Reads
straight off Bookmark/InternshipBookmark rather than folding status into
HackathonOut/InternshipOut, so the existing list/detail endpoints (and
every place that already builds a `bookmarked_ids` set) stay untouched.
"""
from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_profile
from ..models import Bookmark, Hackathon, Internship, InternshipBookmark, Profile
from ..schemas import ApplicationItem, ApplicationList, ApplicationStatusIn
from ..services.matcher import format_inr

router = APIRouter(prefix="/api/applications", tags=["applications"])


def _hackathon_item(row: Hackathon, bookmark: Bookmark, today: date) -> ApplicationItem:
    return ApplicationItem(
        kind="hackathon",
        id=row.id,
        title=row.title,
        url=row.url,
        organizer=row.organizer,
        deadline=row.deadline,
        days_left=(row.deadline - today).days if row.deadline else None,
        status=bookmark.status,
        value_display=f"prize {format_inr(row.prize_inr)}" if row.prize_inr else "—",
        note=bookmark.note,
        updated_at=bookmark.created_at,
    )


def _internship_item(row: Internship, bookmark: InternshipBookmark, today: date) -> ApplicationItem:
    return ApplicationItem(
        kind="internship",
        id=row.id,
        title=row.title,
        url=row.url,
        organizer=row.company,
        deadline=row.deadline,
        days_left=(row.deadline - today).days if row.deadline else None,
        status=bookmark.status,
        value_display=f"stipend {format_inr(row.stipend_inr)}" if row.stipend_inr else "—",
        updated_at=bookmark.created_at,
    )


@router.get("", response_model=ApplicationList)
def list_applications(
    db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)
):
    today = date.today()
    items: list[ApplicationItem] = []

    hbookmarks = db.scalars(
        select(Bookmark).where(Bookmark.profile_id == profile.id)
    ).all()
    if hbookmarks:
        hackathons = {
            h.id: h
            for h in db.scalars(
                select(Hackathon).where(
                    Hackathon.id.in_([b.hackathon_id for b in hbookmarks])
                )
            ).all()
        }
        for b in hbookmarks:
            row = hackathons.get(b.hackathon_id)
            if row is not None:
                items.append(_hackathon_item(row, b, today))

    ibookmarks = db.scalars(
        select(InternshipBookmark).where(InternshipBookmark.profile_id == profile.id)
    ).all()
    if ibookmarks:
        internships = {
            i.id: i
            for i in db.scalars(
                select(Internship).where(
                    Internship.id.in_([b.internship_id for b in ibookmarks])
                )
            ).all()
        }
        for b in ibookmarks:
            row = internships.get(b.internship_id)
            if row is not None:
                items.append(_internship_item(row, b, today))

    far_future = 9999
    items.sort(key=lambda i: i.days_left if i.days_left is not None else far_future)
    return ApplicationList(items=items)


@router.patch("/hackathon/{hackathon_id}/status", response_model=ApplicationItem)
def set_hackathon_status(
    hackathon_id: int,
    payload: ApplicationStatusIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
):
    bookmark = db.scalar(
        select(Bookmark).where(
            Bookmark.profile_id == profile.id, Bookmark.hackathon_id == hackathon_id
        )
    )
    if bookmark is None:
        raise HTTPException(404, "Not in your saved list")
    row = db.get(Hackathon, hackathon_id)
    if row is None:
        raise HTTPException(404, "Hackathon not found")

    bookmark.status = payload.status
    db.commit()
    return _hackathon_item(row, bookmark, date.today())


@router.patch("/internship/{internship_id}/status", response_model=ApplicationItem)
def set_internship_status(
    internship_id: int,
    payload: ApplicationStatusIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
):
    bookmark = db.scalar(
        select(InternshipBookmark).where(
            InternshipBookmark.profile_id == profile.id,
            InternshipBookmark.internship_id == internship_id,
        )
    )
    if bookmark is None:
        raise HTTPException(404, "Not in your saved list")
    row = db.get(Internship, internship_id)
    if row is None:
        raise HTTPException(404, "Internship not found")

    bookmark.status = payload.status
    db.commit()
    return _internship_item(row, bookmark, date.today())
