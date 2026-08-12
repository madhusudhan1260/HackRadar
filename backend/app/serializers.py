"""Turn ORM rows into API payloads (match score, bookmarks, mirrors)."""
from __future__ import annotations

from datetime import date

from .models import Hackathon, Profile
from .schemas import HackathonOut, MatchInfo, Mirror
from .services.matcher import format_inr, score


def to_out(
    row: Hackathon,
    profile: Profile | None = None,
    bookmarked_ids: set[int] | None = None,
    mirrors: list[dict] | None = None,
    today: date | None = None,
) -> HackathonOut:
    today = today or date.today()
    out = HackathonOut.model_validate(row)
    out.days_left = (row.deadline - today).days if row.deadline else None
    out.prize_display = format_inr(row.prize_inr) if row.prize_inr else "—"
    out.bookmarked = bool(bookmarked_ids and row.id in bookmarked_ids)
    out.also_on = [Mirror(**m) for m in (mirrors or [])]
    if profile is not None:
        out.match = MatchInfo(**score(row, profile, today=today))
    return out
