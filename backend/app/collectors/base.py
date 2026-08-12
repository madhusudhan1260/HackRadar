"""Collector contract shared by every source adapter.

A collector's only job is to return `RawHackathon` records. All cleaning,
classification and de-duplication happens downstream in the pipeline, so
adding a new platform means writing one small `fetch()` method.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import httpx

from ..config import settings


@dataclass
class RawHackathon:
    """Loosely-typed record straight from a source. Strings may be messy."""

    source: str
    source_id: str
    url: str
    title: str
    description: str = ""
    organizer: str = ""
    image_url: str = ""
    deadline: date | str | None = None
    start_date: date | str | None = None
    end_date: date | str | None = None
    location: str = ""
    mode_hint: str = ""
    prize_text: str = ""
    prize_currency: str = "USD"
    fee_text: str = ""
    team_text: str = ""
    tags: list[str] = field(default_factory=list)
    status: str = "open"
    raw: dict = field(default_factory=dict)


class Collector:
    """Base class. Subclasses set `name` and implement `fetch`."""

    name: str = "base"
    #: Human-readable note about how this source is accessed.
    access_note: str = ""

    def fetch(self, limit: int = 200) -> list[RawHackathon]:  # pragma: no cover
        raise NotImplementedError

    # -- helpers available to every collector ---------------------------

    @staticmethod
    def client(**kwargs) -> httpx.Client:
        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "application/json, text/html;q=0.9,*/*;q=0.8",
        }
        headers.update(kwargs.pop("headers", {}))
        return httpx.Client(
            headers=headers,
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            **kwargs,
        )
