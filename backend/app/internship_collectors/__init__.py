"""Internship collector registry — mirrors app/collectors/__init__.py."""
from __future__ import annotations

from .adzuna import AdzunaCollector
from .base import InternshipCollector, RawInternship
from .github_tracker import GithubTrackerCollector
from .internshala import InternshalaCollector
from .remotive import RemotiveCollector
from .unstop import UnstopCollector

REGISTRY: dict[str, type[InternshipCollector]] = {
    RemotiveCollector.name: RemotiveCollector,
    GithubTrackerCollector.name: GithubTrackerCollector,
    InternshalaCollector.name: InternshalaCollector,
    AdzunaCollector.name: AdzunaCollector,
    UnstopCollector.name: UnstopCollector,
}


def get_collector(name: str) -> InternshipCollector:
    try:
        return REGISTRY[name]()
    except KeyError:
        raise ValueError(
            f"Unknown internship collector {name!r}. Available: {', '.join(sorted(REGISTRY))}"
        ) from None


def available() -> list[dict]:
    return [
        {"name": name, "access_note": cls.access_note}
        for name, cls in sorted(REGISTRY.items())
    ]


__all__ = ["InternshipCollector", "RawInternship", "REGISTRY", "get_collector", "available"]
