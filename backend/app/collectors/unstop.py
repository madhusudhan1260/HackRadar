"""Unstop collector — DISABLED BY DEFAULT.

Unstop's listing page is backed by a JSON endpoint, but their Terms of Use
restrict automated access, and they offer no documented public API. This
adapter is written so the pipeline is ready the moment you have a legitimate
route in (an official API key, a partner feed, or written permission), but it
is intentionally left out of ENABLED_COLLECTORS.

Before you switch it on:
  1. Read https://unstop.com/terms-and-conditions
  2. Check https://unstop.com/robots.txt for the paths you intend to touch
  3. Prefer emailing them for API access — aggregators usually get it

Enable via:  ENABLED_COLLECTORS=seed,devpost,mlh,unstop
"""
from __future__ import annotations

import time

from .base import Collector, RawHackathon

API = "https://unstop.com/api/public/opportunity/search-result"


class UnstopCollector(Collector):
    name = "unstop"
    access_note = (
        "Off by default: no public API and ToS restrict automated access. "
        "Enable only with permission or an official feed."
    )

    def fetch(self, limit: int = 200) -> list[RawHackathon]:
        out: list[RawHackathon] = []
        with self.client(headers={"Accept": "application/json"}) as client:
            page = 1
            while len(out) < limit and page <= 8:
                resp = client.get(
                    API,
                    params={
                        "opportunity": "hackathons",
                        "page": page,
                        "per_page": 30,
                        "oppstatus": "open",
                    },
                )
                resp.raise_for_status()
                data = resp.json().get("data", {})
                items = data.get("data") or []
                if not items:
                    break
                for item in items:
                    record = self._parse(item)
                    if record:
                        out.append(record)
                page += 1
                time.sleep(1.0)
        return out[:limit]

    def _parse(self, item: dict) -> RawHackathon | None:
        title = (item.get("title") or "").strip()
        slug = item.get("public_url") or item.get("seo_url") or ""
        if not title or not slug:
            return None
        url = slug if slug.startswith("http") else f"https://unstop.com/{slug.lstrip('/')}"

        prizes = item.get("prizes") or []
        prize_text = ""
        if prizes:
            amounts = [str(p.get("cash", "")) for p in prizes if p.get("cash")]
            if amounts:
                prize_text = f"₹{max(amounts, key=lambda a: _to_int(a))}"

        org = (item.get("organisation") or {}).get("name", "")
        region = item.get("region") or ""
        filters = [f.get("name", "") for f in (item.get("filters") or []) if f.get("name")]

        return RawHackathon(
            source=self.name,
            source_id=str(item.get("id") or url),
            url=url,
            title=title,
            description=item.get("subtitle") or item.get("details") or "",
            organizer=org,
            image_url=(item.get("banner_mobile") or {}).get("image_url", ""),
            deadline=item.get("regnRequirements", {}).get("end_regn_dt")
            or item.get("end_date"),
            start_date=item.get("start_date"),
            end_date=item.get("end_date"),
            location=region if region.lower() != "online" else "Online",
            mode_hint=region,
            prize_text=prize_text,
            prize_currency="INR",
            fee_text=str(item.get("regnRequirements", {}).get("reg_fee", "") or ""),
            team_text=(
                f"team {item.get('regnRequirements', {}).get('min_team_size', 1)}"
                f"-{item.get('regnRequirements', {}).get('max_team_size', 4)}"
            ),
            tags=filters,
            raw=item,
        )


def _to_int(value: str) -> int:
    try:
        return int(float(str(value).replace(",", "")))
    except (TypeError, ValueError):
        return 0
