"""Devpost collector.

Devpost serves its own hackathon directory from a public JSON endpoint
(`/api/hackathons`) — the same one their website calls. No auth, no
scraping of rendered HTML. We page through it politely.
"""
from __future__ import annotations

import re
import time

from .base import Collector, RawHackathon

API = "https://devpost.com/api/hackathons"
_TAG_RE = re.compile(r"<[^>]+>")


class DevpostCollector(Collector):
    name = "devpost"
    access_note = "Public JSON API used by devpost.com itself."

    def fetch(self, limit: int = 200) -> list[RawHackathon]:
        out: list[RawHackathon] = []
        with self.client() as client:
            page = 1
            while len(out) < limit and page <= 12:
                resp = client.get(
                    API,
                    params={"page": page, "order_by": "deadline", "status[]": "open"},
                )
                resp.raise_for_status()
                payload = resp.json()
                items = payload.get("hackathons") or []
                if not items:
                    break
                for item in items:
                    record = self._parse(item)
                    if record:
                        out.append(record)
                page += 1
                time.sleep(0.6)  # be a good citizen
        return out[:limit]

    def _parse(self, item: dict) -> RawHackathon | None:
        title = (item.get("title") or "").strip()
        url = item.get("url") or ""
        if not title or not url:
            return None
        if url.startswith("//"):
            url = "https:" + url

        # "submission_period_dates": "Aug 01 - Sep 15, 2026"
        period = item.get("submission_period_dates") or ""
        start, end = _split_period(period)

        themes = [t.get("name", "") for t in (item.get("themes") or []) if t.get("name")]
        location = (item.get("displayed_location") or {}).get("location", "")

        return RawHackathon(
            source=self.name,
            source_id=str(item.get("id") or url),
            url=url,
            title=title,
            description=_clean(item.get("tagline") or ""),
            organizer=item.get("organization_name") or "",
            image_url=_https(item.get("thumbnail_url") or ""),
            deadline=end,
            start_date=start,
            end_date=end,
            location=location,
            mode_hint=location,
            prize_text=_clean(item.get("prize_amount") or ""),
            prize_currency="USD",
            tags=themes,
            status="open" if (item.get("open_state") == "open") else "closed",
            raw=item,
        )


def _clean(value: str) -> str:
    return _TAG_RE.sub("", value or "").replace("&nbsp;", " ").strip()


def _https(url: str) -> str:
    return "https:" + url if url.startswith("//") else url


def _split_period(period: str) -> tuple[str, str]:
    """'Aug 01 - Sep 15, 2026' -> ('Aug 01 2026', 'Sep 15 2026')."""
    if not period:
        return "", ""
    year_match = re.search(r"(\d{4})", period)
    year = year_match.group(1) if year_match else ""
    parts = re.split(r"\s*[-–]\s*", period, maxsplit=1)
    if len(parts) == 2:
        start = parts[0].strip().rstrip(",")
        end = parts[1].strip()
        if year and year not in start:
            start = f"{start} {year}"
        return start, end
    return "", period.strip()
