"""Internshala collector — DISABLED BY DEFAULT.

India's largest internship platform would make this dataset far more
useful locally, but their Terms of Use explicitly prohibit data mining /
scraping, and they publish no public API. Written so the pipeline is ready
the moment there is a legitimate route in — an official partnership or a
documented API — but it must stay out of ENABLED_INTERNSHIP_COLLECTORS
until then.

Before enabling:
  1. Read https://internshala.com/terms-and-conditions
  2. Contact Internshala for API access rather than scraping
"""
from __future__ import annotations

from .base import InternshipCollector, RawInternship


class InternshalaCollector(InternshipCollector):
    name = "internshala"
    access_note = (
        "Off by default: Terms of Use prohibit data mining and there is no "
        "public API. Enable only with an official feed or written permission."
    )

    def fetch(self, limit: int = 200) -> list[RawInternship]:
        raise NotImplementedError(
            "Internshala has no permitted access path yet — see the module "
            "docstring before enabling this collector."
        )
