"""Major League Hacking (MLH) season collector.

MLH publishes each season's events as schema.org `Event` microdata on its
public season pages — structured start/end dates, attendance mode, postal
address and a free-entry flag. We read those `itemprop` values rather than
guessing from rendered text, which makes this collector unusually reliable
for an HTML source.
"""
from __future__ import annotations

from datetime import date

from bs4 import BeautifulSoup, Tag

from .base import Collector, RawHackathon

SEASON_URL = "https://mlh.io/seasons/{year}/events"

_ATTENDANCE_MODE = {
    "OnlineEventAttendanceMode": "online",
    "OfflineEventAttendanceMode": "offline",
    "MixedEventAttendanceMode": "hybrid",
}

# ISO country codes seen on MLH, expanded so downstream India detection works.
_COUNTRY_NAMES = {
    "IN": "India", "US": "United States", "CA": "Canada", "GB": "United Kingdom",
    "DE": "Germany", "FR": "France", "NL": "Netherlands", "ES": "Spain",
    "IT": "Italy", "PL": "Poland", "BR": "Brazil", "MX": "Mexico",
    "AU": "Australia", "SG": "Singapore", "AE": "United Arab Emirates",
    "NG": "Nigeria", "KE": "Kenya", "ZA": "South Africa", "JP": "Japan",
}


class MLHCollector(Collector):
    name = "mlh"
    access_note = "Public season pages, read via schema.org Event microdata."

    def fetch(self, limit: int = 200) -> list[RawHackathon]:
        out: list[RawHackathon] = []
        seen: set[str] = set()

        with self.client() as client:
            for year in _seasons():
                try:
                    resp = client.get(SEASON_URL.format(year=year))
                    resp.raise_for_status()
                except Exception:
                    continue

                for record in self._parse_page(resp.text, year):
                    if record.source_id in seen:
                        continue
                    seen.add(record.source_id)
                    out.append(record)
                    if len(out) >= limit:
                        return out
        return out

    def _parse_page(self, html: str, year: int) -> list[RawHackathon]:
        soup = BeautifulSoup(html, "html.parser")
        records: list[RawHackathon] = []

        for card in soup.select('[itemtype*="schema.org/Event"]'):
            url = _prop(card, "url") or card.get("href", "")
            if not url:
                continue

            title = _title(card)
            if not title:
                continue

            mode = _ATTENDANCE_MODE.get(
                (_prop(card, "eventAttendanceMode") or "").rsplit("/", 1)[-1], ""
            )
            location = _location(card)
            free = (_prop(card, "isAccessibleForFree") or "").lower() == "true"

            start = _prop(card, "startDate")
            end = _prop(card, "endDate")

            records.append(
                RawHackathon(
                    source=self.name,
                    source_id=url,
                    url=url,
                    title=title,
                    description=(
                        f"{title} is part of the MLH {year} season. "
                        f"{'Online event.' if mode == 'online' else f'Hosted in {location}.' if location else ''} "
                        "Open to students; beginners welcome."
                    ).strip(),
                    organizer="Major League Hacking",
                    image_url=_prop(card, "image") or "",
                    # MLH lists event dates, not a separate registration
                    # deadline — the event start is the actionable date.
                    deadline=start,
                    start_date=start,
                    end_date=end,
                    location=location or ("Online" if mode == "online" else ""),
                    mode_hint=mode or location,
                    fee_text="Free entry" if free else "",
                    team_text="team 1-4",
                    tags=["Student", "MLH"],
                    raw={"season": year, "mode": mode, "free": free},
                )
            )
        return records


# --------------------------------------------------------------------------


def _prop(card: Tag, name: str) -> str:
    """Read a schema.org itemprop, preferring @content over text."""
    el = card.select_one(f'[itemprop="{name}"]')
    if el is None:
        return ""
    return (el.get("content") or el.get_text(" ", strip=True) or "").strip()


def _title(card: Tag) -> str:
    """The event name sits in the card heading, not in an itemprop."""
    heading = card.select_one("h1, h2, h3, h4, h5")
    if heading:
        text = heading.get_text(" ", strip=True)
        if text:
            return text
    img = card.select_one("img[alt]")
    if img:
        alt = img.get("alt", "").replace(" background", "").strip()
        if alt:
            return alt
    return ""


def _location(card: Tag) -> str:
    """Build 'City, Region, Country' from the PostalAddress microdata."""
    city = _prop(card, "addressLocality")
    region = _prop(card, "addressRegion")
    country_code = _prop(card, "addressCountry")
    country = _COUNTRY_NAMES.get(country_code.upper(), country_code)

    parts = [p for p in (city, region, country) if p]
    if parts:
        return ", ".join(parts)
    return _prop(card, "location")


def _seasons() -> list[int]:
    """Current and next MLH season, so upcoming events are always covered."""
    today = date.today()
    return [today.year, today.year + 1] if today.month >= 6 else [today.year]
