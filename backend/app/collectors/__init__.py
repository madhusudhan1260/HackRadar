"""Collector registry.

Add a new platform in three steps:
  1. write `mysource.py` with a `Collector` subclass
  2. import it here and add it to `REGISTRY`
  3. add its name to ENABLED_COLLECTORS in .env
"""
from __future__ import annotations

from .base import Collector, RawHackathon
from .devpost import DevpostCollector
from .mlh import MLHCollector
from .seed import SeedCollector
from .unstop import UnstopCollector

REGISTRY: dict[str, type[Collector]] = {
    SeedCollector.name: SeedCollector,
    DevpostCollector.name: DevpostCollector,
    MLHCollector.name: MLHCollector,
    UnstopCollector.name: UnstopCollector,
}


def get_collector(name: str) -> Collector:
    try:
        return REGISTRY[name]()
    except KeyError:
        raise ValueError(
            f"Unknown collector {name!r}. Available: {', '.join(sorted(REGISTRY))}"
        ) from None


def available() -> list[dict]:
    return [
        {"name": name, "access_note": cls.access_note}
        for name, cls in sorted(REGISTRY.items())
    ]


__all__ = ["Collector", "RawHackathon", "REGISTRY", "get_collector", "available"]
