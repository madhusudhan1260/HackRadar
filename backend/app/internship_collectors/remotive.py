"""Remotive collector.

Remotive publishes a free, documented, no-key-required public API — the
one they intend third parties to use (github.com/remotive-com/remote-jobs-api).
Their usage terms ask for at most a handful of requests a day and a link
back to Remotive; both are satisfied here (fetched once per ingest cycle,
every listing keeps its original Remotive URL as the apply link).
"""
from __future__ import annotations

from .base import InternshipCollector, RawInternship

API = "https://remotive.com/api/remote-jobs"


class RemotiveCollector(InternshipCollector):
    name = "remotive"
    access_note = "Remotive's public API (remotive.com/api/remote-jobs) — free, documented, no key."

    def fetch(self, limit: int = 200) -> list[RawInternship]:
        out: list[RawInternship] = []
        with self.client() as client:
            resp = client.get(API, params={"search": "intern"})
            resp.raise_for_status()
            items = resp.json().get("jobs") or []

        for item in items:
            record = self._parse(item)
            if record:
                out.append(record)
            if len(out) >= limit:
                break
        return out

    def _parse(self, item: dict) -> RawInternship | None:
        # The search endpoint has no strict internship filter, so keep only
        # postings that actually say so — either the platform's own
        # classification or the title itself.
        job_type = (item.get("job_type") or "").lower()
        title = (item.get("title") or "").strip()
        if job_type != "internship" and "intern" not in title.lower():
            return None

        url = item.get("url") or ""
        if not title or not url:
            return None

        return RawInternship(
            source=self.name,
            source_id=str(item.get("id") or url),
            url=url,
            title=title,
            company=item.get("company_name") or "",
            company_url="",
            description=item.get("description") or "",
            posted_date=item.get("publication_date"),
            location=item.get("candidate_required_location") or "",
            mode_hint="remote",  # Remotive is remote-only by definition.
            stipend_text=item.get("salary") or "",
            stipend_currency="USD",
            tags=[item.get("category")] if item.get("category") else [],
            raw=item,
        )
