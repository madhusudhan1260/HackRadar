"""Collector contract for internship sources — the internship equivalent of
`app/collectors/base.py`. Kept as a separate small hierarchy rather than
generalising the hackathon one: the two domains diverge enough (stipend vs
prize, company vs organiser, no team size) that sharing a base class would
mean one or the other bending to fit, which tends to rot both.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import httpx

from ..config import settings


@dataclass
class RawInternship:
    """Loosely-typed record straight from a source. Strings may be messy."""

    source: str
    source_id: str
    url: str
    title: str
    company: str = ""
    company_url: str = ""
    description: str = ""
    deadline: date | str | None = None
    posted_date: date | str | None = None
    term: str = ""
    location: str = ""
    mode_hint: str = ""
    stipend_text: str = ""
    stipend_currency: str = "INR"
    duration_text: str = ""
    eligibility: str = ""
    tags: list[str] = field(default_factory=list)
    status: str = "open"
    raw: dict = field(default_factory=dict)


class InternshipCollector:
    """Base class. Subclasses set `name` and implement `fetch`."""

    name: str = "base"
    access_note: str = ""

    def fetch(self, limit: int = 200) -> list[RawInternship]:  # pragma: no cover
        raise NotImplementedError

    @staticmethod
    def client(**kwargs) -> httpx.Client:
        headers = {
            "User-Agent": settings.USER_AGENT,
            "Accept": "application/json, text/plain;q=0.9,*/*;q=0.8",
        }
        headers.update(kwargs.pop("headers", {}))
        return httpx.Client(
            headers=headers,
            timeout=settings.HTTP_TIMEOUT,
            follow_redirects=True,
            **kwargs,
        )
