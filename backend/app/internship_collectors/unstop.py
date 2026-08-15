"""Unstop internships collector — DISABLED BY DEFAULT.

Same site, same restriction as collectors/unstop.py (the hackathon
version): their listing pages are backed by a JSON endpoint
(unstop.com/api/public/opportunity/search-result?opportunity=internships),
but their Terms of Use restrict automated access and there is no
documented public API for third parties. That reasoning is site-wide, not
opportunity-type-specific, so it applies here exactly as it did for
hackathons. Written so the pipeline is ready the moment there's a
legitimate route in, but intentionally left out of
ENABLED_INTERNSHIP_COLLECTORS.

Before you switch it on:
  1. Read https://unstop.com/terms-and-conditions
  2. Check https://unstop.com/robots.txt for the paths you intend to touch
  3. Prefer emailing them for API access — aggregators usually get it

Enable via:  ENABLED_INTERNSHIP_COLLECTORS=remotive,github-tracker,unstop
"""
from __future__ import annotations

from .base import InternshipCollector, RawInternship


class UnstopCollector(InternshipCollector):
    name = "unstop"
    access_note = (
        "Off by default: no public API and ToS restrict automated access "
        "(same finding as the hackathons Unstop collector). Enable only "
        "with permission or an official feed."
    )

    def fetch(self, limit: int = 200) -> list[RawInternship]:
        raise NotImplementedError(
            "Unstop has no permitted access path yet — see the module "
            "docstring before enabling this collector."
        )
