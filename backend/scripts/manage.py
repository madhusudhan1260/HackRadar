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
from app.models import Hackathon, Profile  # noqa: E402
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
    """Run deadline alerts for every registered user."""
    init_db()
    db = SessionLocal()
    try:
        profiles = db.scalars(select(Profile)).all()
        if not profiles:
            print("No profiles yet — register an account first.")
            return

        for profile in profiles:
            result = dispatch(db, profile, dry_run=args.dry_run)
            print(f"\n{profile.name} (profile {profile.id})")
            print(f"  alerts: {len(result['alerts'])}  sent: {result['sent']}")
            for alert in result["alerts"]:
                print(f"    [{alert['days_left']}d] {alert['title']} — {alert['match_score']}%")
            if result.get("note"):
                print(f"    note: {result['note']}")
    finally:
        db.close()


def cmd_create_admin(args) -> None:
    """Create, update or promote THE admin account.

    The app is deliberately single-admin: exactly one account may hold the
    admin role. Creating another requires --replace, which demotes the
    current one, so admin access can never quietly spread.
    """
    import getpass
    import os

    from sqlalchemy import select as sa_select

    from app.models import User
    from app.security import (
        hash_password,
        normalize_phone,
        normalize_username,
        password_problem,
        phone_problem,
        username_problem,
    )
    from app.services.auth import ensure_profile, revoke_all_sessions

    init_db()
    db = SessionLocal()
    try:
        username = normalize_username(args.username or input("Admin username: "))
        problem = username_problem(username)
        if problem:
            print(f"error: {problem}")
            return

        existing_admins = db.scalars(sa_select(User).where(User.role == "admin")).all()
        others = [a for a in existing_admins if a.username != username]
        if others and not args.replace:
            print("error: an admin already exists — " + ", ".join(a.username for a in others))
            print("       Re-run with --replace to demote it and take over admin access.")
            return

        # Password: prefer the environment so it never reaches shell history
        # or the process list.
        password = os.environ.get("HACKRADAR_ADMIN_PASSWORD") or args.password
        if not password:
            password = getpass.getpass("Password: ")
            if password != getpass.getpass("Confirm password: "):
                print("error: passwords do not match.")
                return
        problem = password_problem(password)
        if problem:
            print(f"error: {problem}")
            return

        account = db.scalar(sa_select(User).where(User.username == username))

        if account is not None:
            account.role = "admin"
            account.status = "active"
            account.phone_verified = True
            account.password_hash = hash_password(password)
            account.failed_attempts = 0
            account.locked_until = None
            if args.name:
                account.name = args.name.strip()
            if args.phone:
                phone = normalize_phone(args.phone)
                problem = phone_problem(phone)
                if problem:
                    print(f"error: {problem}")
                    return
                clash = db.scalar(
                    sa_select(User).where(User.phone == phone, User.id != account.id)
                )
                if clash is not None:
                    print(f"error: {phone} already belongs to '{clash.username}'.")
                    return
                account.phone = phone
            db.commit()
            # A credential change invalidates every existing session.
            revoke_all_sessions(db, account.id)
            ensure_profile(db, account)
            print(f"Updated admin account '{username}' ({account.phone}).")
        else:
            name = args.name or input("Full name: ")
            phone = normalize_phone(args.phone or input("Phone (e.g. +919876543210): "))
            problem = phone_problem(phone)
            if problem:
                print(f"error: {problem}")
                return
            if db.scalar(sa_select(User).where(User.phone == phone)) is not None:
                print("error: that phone number is already registered.")
                return

            account = User(
                username=username,
                name=name.strip(),
                phone=phone,
                password_hash=hash_password(password),
                role="admin",
                status="active",
                phone_verified=True,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            ensure_profile(db, account)
            print(f"Admin created: {username} ({phone})")

        # Demote anyone else who held admin, and cut their sessions.
        for other in others:
            other.role = "user"
            db.commit()
            revoke_all_sessions(db, other.id)
            print(f"Demoted '{other.username}' to a normal user.")

        print("\nThis is now the only account with admin access.")
        print("Sign in via the Admin tab on the login page.")
    finally:
        db.close()


def cmd_delete_user(args) -> None:
    """Remove an account and everything attached to it."""
    from sqlalchemy import select as sa_select

    from app.models import AuthSession, Bookmark, OtpCode, Profile, User
    from app.security import normalize_username

    init_db()
    db = SessionLocal()
    try:
        username = normalize_username(args.username)
        user = db.scalar(sa_select(User).where(User.username == username))
        if user is None:
            print(f"error: no account named '{username}'.")
            return
        if user.role == "admin":
            print("error: refusing to delete the admin account.")
            return

        if not args.yes:
            answer = input(f"Delete '{username}' ({user.name}, {user.phone})? [y/N] ")
            if answer.strip().lower() != "y":
                print("Aborted.")
                return

        for model in (OtpCode, AuthSession):
            for row in db.scalars(sa_select(model).where(model.user_id == user.id)).all():
                db.delete(row)
        for profile in db.scalars(sa_select(Profile).where(Profile.user_id == user.id)).all():
            for mark in db.scalars(
                sa_select(Bookmark).where(Bookmark.profile_id == profile.id)
            ).all():
                db.delete(mark)
            db.delete(profile)
        db.delete(user)
        db.commit()
        print(f"Deleted '{username}'.")
    finally:
        db.close()


def cmd_users(args) -> None:
    from sqlalchemy import select as sa_select

    from app.models import User

    init_db()
    db = SessionLocal()
    try:
        users = db.scalars(sa_select(User).order_by(User.created_at.desc())).all()
        if not users:
            print("No users registered yet.")
            return
        print(f"{'username':<20} {'name':<22} {'phone':<16} {'role':<6} {'status':<8} logins")
        print("-" * 84)
        for u in users:
            print(
                f"{u.username:<20} {u.name[:20]:<22} {u.phone:<16} "
                f"{u.role:<6} {u.status:<8} {u.login_count}"
            )
    finally:
        db.close()


def cmd_test_sms(args) -> None:
    """Prove the SMS provider is configured correctly, end to end."""
    from app.security import normalize_phone, phone_problem
    from app.services.sms import provider_status, send_test

    status = provider_status()
    print(f"provider   : {status['provider']}")
    print(f"configured : {status['configured']}")
    print(f"live SMS   : {status['is_live']}")
    print(f"note       : {status['note']}\n")

    if not status["configured"]:
        print("Fix the credentials in backend/.env first, then re-run this.")
        return

    if not status["is_live"]:
        print(
            "SMS_PROVIDER=console, so nothing will actually be texted.\n"
            "Set SMS_PROVIDER=twilio or msg91 with credentials to send for real."
        )
        if not args.to:
            return

    phone = normalize_phone(args.to or input("Send a test SMS to (e.g. +919876543210): "))
    problem = phone_problem(phone)
    if problem:
        print(f"error: {problem}")
        return

    print(f"Sending test message to {phone} …")
    result = send_test(phone)
    if result.delivered:
        print(f"\n  OK — {result.note}")
        if status["is_live"]:
            print("  Check the handset. If nothing arrives within a minute, the")
            print("  provider accepted it but the carrier dropped it — check the")
            print("  provider's delivery logs (DLT template issues are the usual cause).")
    else:
        print(f"\n  FAILED — {result.note}")


def cmd_purge_source(args) -> None:
    """Delete every listing that came from one collector."""
    from sqlalchemy import select as sa_select

    from app.models import Bookmark, Hackathon

    init_db()
    db = SessionLocal()
    try:
        rows = db.scalars(
            sa_select(Hackathon).where(Hackathon.source == args.source)
        ).all()
        if not rows:
            print(f"Nothing stored from '{args.source}'.")
            return

        ids = {r.id for r in rows}
        marks = db.scalars(
            sa_select(Bookmark).where(Bookmark.hackathon_id.in_(ids))
        ).all()

        if not args.yes:
            print(f"About to delete {len(rows)} listing(s) from '{args.source}'")
            print(f"and {len(marks)} bookmark(s) pointing at them.")
            if input("Continue? [y/N] ").strip().lower() != "y":
                print("Aborted.")
                return

        for mark in marks:
            db.delete(mark)
        for row in rows:
            db.delete(row)
        db.commit()
        print(f"Deleted {len(rows)} listing(s) from '{args.source}'.")
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

    p_admin = sub.add_parser("create-admin", help="Create or promote an admin account")
    p_admin.add_argument("--username")
    p_admin.add_argument("--name")
    p_admin.add_argument("--phone")
    p_admin.add_argument(
        "--password",
        help="Skips the prompt. Prefer HACKRADAR_ADMIN_PASSWORD — an argument "
        "lands in your shell history and the process list.",
    )
    p_admin.add_argument(
        "--replace",
        action="store_true",
        help="Demote any existing admin so this account takes over.",
    )
    p_admin.set_defaults(func=cmd_create_admin)

    p_del = sub.add_parser("delete-user", help="Delete a (non-admin) account")
    p_del.add_argument("username")
    p_del.add_argument("--yes", action="store_true")
    p_del.set_defaults(func=cmd_delete_user)

    p_sms = sub.add_parser("test-sms", help="Check SMS provider config and send a test")
    p_sms.add_argument("--to", help="Destination phone number, e.g. +919876543210")
    p_sms.set_defaults(func=cmd_test_sms)

    p_users = sub.add_parser("users", help="List registered accounts")
    p_users.set_defaults(func=cmd_users)

    p_purge = sub.add_parser("purge-source", help="Delete all listings from one source")
    p_purge.add_argument("source", help="Collector name, e.g. seed")
    p_purge.add_argument("--yes", action="store_true")
    p_purge.set_defaults(func=cmd_purge_source)

    p_reset = sub.add_parser("reset", help="Drop and recreate all tables")
    p_reset.add_argument("--yes", action="store_true")
    p_reset.set_defaults(func=cmd_reset)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
