#!/usr/bin/env python
"""Command line entry point for ingestion and maintenance.

    python scripts/manage.py ingest                # run enabled collectors
    python scripts/manage.py ingest --source seed  # run one collector
    python scripts/manage.py stats                 # what's in the database
    python scripts/manage.py notify --dry-run      # preview alerts
    python scripts/manage.py reset                 # drop and recreate tables
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import func, select  # noqa: E402

from app.config import settings  # noqa: E402
from app.db import Base, SessionLocal, engine, init_db  # noqa: E402
from app.models import Hackathon  # noqa: E402
from app.routers.profile import current_profile  # noqa: E402
from app.services import pipeline  # noqa: E402
from app.services.notifier import dispatch  # noqa: E402


def cmd_ingest(args) -> None:
    init_db()
    db = SessionLocal()
    try:
        sources = [args.source] if args.source else None
        results = pipeline.run_all(db, sources=sources, limit=args.limit)
        closed = pipeline.close_expired(db)
        for r in results:
            status = "ok" if r["ok"] else f"FAILED ({r['error']})"
            print(
                f"{r['source']:>10}: fetched={r['fetched']:<4} "
                f"new={r['created']:<4} updated={r['updated']:<4} {status}"
            )
        print(f"{'':>10}  marked {closed} past-deadline listing(s) closed")
    finally:
        db.close()


def cmd_stats(args) -> None:
    init_db()
    db = SessionLocal()
    try:
        total = db.scalar(select(func.count(Hackathon.id))) or 0
        print(f"Total listings: {total}")
        by_source = db.execute(
            select(Hackathon.source, func.count(Hackathon.id)).group_by(Hackathon.source)
        ).all()
        for source, count in sorted(by_source, key=lambda kv: -kv[1]):
            print(f"  {source:>10}: {count}")

        cats: dict[str, int] = {}
        for row in db.scalars(select(Hackathon)).all():
            for cat in row.categories or []:
                cats[cat] = cats.get(cat, 0) + 1
        print("\nBy category:")
        for cat, count in sorted(cats.items(), key=lambda kv: -kv[1]):
            print(f"  {cat:>16}: {count}")
    finally:
        db.close()


def cmd_notify(args) -> None:
    init_db()
    db = SessionLocal()
    try:
        profile = current_profile(db)
        result = dispatch(db, profile, dry_run=args.dry_run)
        print(f"alerts: {len(result['alerts'])}  sent: {result['sent']}")
        for alert in result["alerts"]:
            print(f"  [{alert['days_left']}d] {alert['title']} — {alert['match_score']}%")
        if result.get("note"):
            print(f"\nnote: {result['note']}")
    finally:
        db.close()


def cmd_reset(args) -> None:
    if not args.yes:
        confirm = input("Drop all tables and recreate? [y/N] ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return
    Base.metadata.drop_all(bind=engine)
    init_db()
    print(f"Reset {settings.DATABASE_URL}")


def main() -> None:
    parser = argparse.ArgumentParser(description="HackRadar management commands")
    sub = parser.add_subparsers(dest="command", required=True)

    p_ingest = sub.add_parser("ingest", help="Collect hackathons from sources")
    p_ingest.add_argument("--source", help="Run a single collector by name")
    p_ingest.add_argument("--limit", type=int, default=200)
    p_ingest.set_defaults(func=cmd_ingest)

    p_stats = sub.add_parser("stats", help="Show database contents")
    p_stats.set_defaults(func=cmd_stats)

    p_notify = sub.add_parser("notify", help="Send deadline alerts")
    p_notify.add_argument("--dry-run", action="store_true")
    p_notify.set_defaults(func=cmd_notify)

    p_reset = sub.add_parser("reset", help="Drop and recreate all tables")
    p_reset.add_argument("--yes", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
