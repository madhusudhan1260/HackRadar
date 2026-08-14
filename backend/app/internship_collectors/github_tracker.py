"""GitHub-hosted internship tracker collector.

Consumes the merged, deduplicated listings.json published by
github.com/SuryaHarikrishnan/2027-internship-tracker, itself an aggregation
of the SimplifyJobs and vanshb03 open internship lists. MIT-licensed, with
an ATTRIBUTION.md that names the upstream projects — the `source` field on
every listing is set from the record's own "source" value (e.g. "Simplify")
so that attribution survives into the UI rather than being flattened away.

Mostly US tech internships. No listing carries a firm application deadline;
`terms` ("Summer 2026") is stored as-is and shown in place of a countdown.
"""
from __future__ import annotations

from datetime import datetime

from .base import InternshipCollector, RawInternship

FEED = (
    "https://raw.githubusercontent.com/SuryaHarikrishnan/"
    "2027-internship-tracker/master/data/listings.json"
)


class GithubTrackerCollector(InternshipCollector):
    name = "github-tracker"
    access_note = (
        "MIT-licensed aggregated JSON feed (github.com/SuryaHarikrishnan/"
        "2027-internship-tracker), itself crediting SimplifyJobs and vanshb03."
    )

    def fetch(self, limit: int = 300) -> list[RawInternship]:
        out: list[RawInternship] = []
        with self.client() as client:
            resp = client.get(FEED)
            resp.raise_for_status()
            items = resp.json()
            if not isinstance(items, list):
                items = items.get("listings", [])

        for item in items:
            if not item.get("active", True) or item.get("is_visible") is False:
                continue
            record = self._parse(item)
            if record:
                out.append(record)
            if len(out) >= limit:
                break
        return out

    def _parse(self, item: dict) -> RawInternship | None:
        title = (item.get("title") or "").strip()
        url = item.get("url") or ""
        if not title or not url:
            return None

        locations = item.get("locations") or []
        location = ", ".join(locations[:2])
        remote = any("remote" in loc.lower() for loc in locations)

        terms = item.get("terms") or []
        degrees = item.get("degrees") or []

        return RawInternship(
            source=item.get("source") or self.name,
            source_id=str(item.get("id") or url),
            url=url,
            title=title,
            company=item.get("company_name") or "",
            company_url=item.get("company_url") or "",
            description=f"{title} at {item.get('company_name', '')}. "
            f"{'Remote.' if remote else location + '.' if location else ''}",
            posted_date=_from_epoch(item.get("date_posted")),
            term=", ".join(terms),
            location=location,
            mode_hint="remote" if remote else "onsite",
            eligibility=", ".join(degrees),
            tags=[item.get("category")] if item.get("category") else [],
            raw=item,
        )


def _from_epoch(value) -> str | None:
    if not value:
        return None
    try:
        return datetime.utcfromtimestamp(int(value)).date().isoformat()
    except (TypeError, ValueError, OSError):
        return None
