"""Collapse the same event listed on multiple platforms into one card."""
from __future__ import annotations

from ..models import Hackathon

# Prefer sources that carry richer structured data when picking the winner.
_SOURCE_RANK = {"unstop": 3, "devpost": 3, "hackerearth": 2, "mlh": 2, "seed": 1}


def _completeness(row: Hackathon) -> tuple:
    return (
        _SOURCE_RANK.get(row.source, 1),
        bool(row.deadline),
        bool(row.prize_inr),
        len(row.tags or []),
        len(row.description or ""),
    )


def collapse(rows: list[Hackathon]) -> list[tuple[Hackathon, list[dict]]]:
    """Group rows by cluster key.

    Returns [(winning_row, [{source, url} for the other listings]), ...],
    preserving the order the winners appeared in the input.
    """
    groups: dict[str, list[Hackathon]] = {}
    order: list[str] = []
    for row in rows:
        key = row.cluster_key or f"__id{row.id}"
        if key not in groups:
            groups[key] = []
            order.append(key)
        groups[key].append(row)

    result: list[tuple[Hackathon, list[dict]]] = []
    for key in order:
        members = groups[key]
        winner = max(members, key=_completeness)
        mirrors = [
            {"source": m.source, "url": m.url}
            for m in members
            if m.id != winner.id
        ]
        result.append((winner, mirrors))
    return result
