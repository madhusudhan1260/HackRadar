"""Adzuna collector — real, India-focused internships.

Adzuna runs a self-serve job-search API built specifically for third-party
use ("Enhance your own website with Adzuna's search function and massive
database of ads" — developer.adzuna.com/terms), unlike Unstop/Internshala
which have no such route. India ('in') is a genuinely supported country —
confirmed directly against the live API rather than assumed from docs.

Needs a free ADZUNA_APP_ID / ADZUNA_APP_KEY pair — instant self-serve
signup at https://developer.adzuna.com/signup, no card required, ~1,000
calls/month on the free tier. Sign up yourself (this collector can't
create an account on your behalf) and set both as env vars; until then
fetch() logs why and returns nothing rather than failing ingestion for
every other source.
"""
from __future__ import annotations

import logging

from ..config import settings
from .base import InternshipCollector, RawInternship

log = logging.getLogger(__name__)

API = "https://api.adzuna.com/v1/api/jobs/{country}/search/{page}"


class AdzunaCollector(InternshipCollector):
    name = "adzuna"
    access_note = (
        "Real API, India-supported. Needs a free ADZUNA_APP_ID/ADZUNA_APP_KEY "
        "(instant self-serve signup at developer.adzuna.com) — off until both are set."
    )

    def fetch(self, limit: int = 200) -> list[RawInternship]:
        if not (settings.ADZUNA_APP_ID and settings.ADZUNA_APP_KEY):
            log.info(
                "Adzuna collector skipped: set ADZUNA_APP_ID/ADZUNA_APP_KEY "
                "(free signup at developer.adzuna.com) to enable it."
            )
            return []

        country = (settings.ADZUNA_COUNTRY or "in").lower()
        currency = "INR" if country == "in" else "USD"

        out: list[RawInternship] = []
        with self.client(headers={"Accept": "application/json"}) as client:
            page = 1
            while len(out) < limit and page <= 10:
                resp = client.get(
                    API.format(country=country, page=page),
                    params={
                        "app_id": settings.ADZUNA_APP_ID,
                        "app_key": settings.ADZUNA_APP_KEY,
                        "what": "internship",
                        "results_per_page": 50,
                        "sort_by": "date",
                    },
                )
                if resp.status_code == 401:
                    log.warning("Adzuna rejected the API credentials (401) — check ADZUNA_APP_ID/ADZUNA_APP_KEY.")
                    break
                resp.raise_for_status()
                items = resp.json().get("results") or []
                if not items:
                    break
                for item in items:
                    record = self._parse(item, currency)
                    if record:
                        out.append(record)
                page += 1
        return out[:limit]

    def _parse(self, item: dict, currency: str) -> RawInternship | None:
        title = (item.get("title") or "").strip()
        url = item.get("redirect_url") or ""
        if not title or not url:
            return None

        # `what=internship` is a tokenised text match over title+description,
        # so it still lets through e.g. "internship program manager" (a real
        # full-time role that just mentions internships). Keep only postings
        # that read like an actual internship.
        description = item.get("description") or ""
        if "intern" not in f"{title} {description}".lower():
            return None

        company = (item.get("company") or {}).get("display_name", "")
        location = (item.get("location") or {}).get("display_name", "")
        category = (item.get("category") or {}).get("label", "")

        salary_min = item.get("salary_min")
        salary_max = item.get("salary_max")
        stipend_text = ""
        if salary_min or salary_max:
            figure = salary_max or salary_min
            stipend_text = str(int(figure))

        return RawInternship(
            source=self.name,
            source_id=str(item.get("id") or url),
            url=url,
            title=title,
            company=company,
            description=description,
            posted_date=item.get("created"),
            location=location,
            mode_hint=location,
            stipend_text=stipend_text,
            stipend_currency=currency,
            tags=[category] if category else [],
            raw=item,
        )
