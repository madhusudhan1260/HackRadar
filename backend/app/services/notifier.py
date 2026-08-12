"""Deadline notifications over email and Telegram.

`pending_alerts` decides *what* should fire (and is safe to call any time —
it never sends). `dispatch` actually sends and records the send so the same
alert never goes out twice.
"""
from __future__ import annotations

import logging
import smtplib
from datetime import date
from email.message import EmailMessage

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Bookmark, Hackathon, NotificationLog, Profile
from .matcher import format_inr, score

log = logging.getLogger(__name__)


def pending_alerts(db: Session, profile: Profile, today: date | None = None) -> list[dict]:
    """Alerts that are due but not yet sent, newest deadline first.

    An event qualifies if it is bookmarked, or if it scores at least the
    profile's `notify_min_score`.
    """
    today = today or date.today()
    windows = sorted(set(profile.notify_days_before or [7, 3, 1]))
    if not windows:
        return []

    horizon = max(windows)
    rows = db.scalars(
        select(Hackathon).where(
            Hackathon.status == "open",
            Hackathon.deadline.is_not(None),
        )
    ).all()

    bookmarked = {
        b.hackathon_id
        for b in db.scalars(
            select(Bookmark).where(Bookmark.profile_id == profile.id)
        ).all()
    }
    already_sent = {
        (n.hackathon_id, n.kind)
        for n in db.scalars(
            select(NotificationLog).where(NotificationLog.profile_id == profile.id)
        ).all()
    }

    alerts: list[dict] = []
    for row in rows:
        days_left = (row.deadline - today).days
        if days_left < 0 or days_left > horizon:
            continue
        if days_left not in windows:
            continue

        kind = f"deadline-{days_left}d"
        if (row.id, kind) in already_sent:
            continue

        match = score(row, profile, today=today)
        is_bookmarked = row.id in bookmarked
        if not is_bookmarked and match["score"] < (profile.notify_min_score or 0):
            continue

        alerts.append(
            {
                "hackathon": row,
                "kind": kind,
                "days_left": days_left,
                "match": match,
                "bookmarked": is_bookmarked,
            }
        )

    alerts.sort(key=lambda a: (a["days_left"], -a["match"]["score"]))
    return alerts


def dispatch(db: Session, profile: Profile, dry_run: bool = False) -> dict:
    """Send every pending alert. `dry_run=True` previews without sending."""
    alerts = pending_alerts(db, profile)
    if not alerts:
        return {"sent": 0, "channels": [], "alerts": []}

    summary = [_summarise(a) for a in alerts]
    if dry_run:
        return {"sent": 0, "channels": ["dry-run"], "alerts": summary}

    channels: list[str] = []
    body_text = _render_text(profile, alerts)

    if settings.SMTP_HOST and profile.email:
        if _send_email(profile.email, f"{len(alerts)} hackathon deadline(s) coming up", body_text):
            channels.append("email")

    chat_id = profile.telegram_chat_id or settings.TELEGRAM_CHAT_ID
    if settings.TELEGRAM_BOT_TOKEN and chat_id:
        if _send_telegram(chat_id, body_text):
            channels.append("telegram")

    if not channels:
        # Nothing configured — leave the alerts unlogged so they fire once a
        # channel is set up, and let the caller show them in-app instead.
        return {
            "sent": 0,
            "channels": [],
            "alerts": summary,
            "note": "No delivery channel configured. Set SMTP_* or TELEGRAM_* in .env.",
        }

    for alert in alerts:
        db.add(
            NotificationLog(
                profile_id=profile.id,
                hackathon_id=alert["hackathon"].id,
                kind=alert["kind"],
                channel=",".join(channels),
            )
        )
    db.commit()

    return {"sent": len(alerts), "channels": channels, "alerts": summary}


# --------------------------------------------------------------------------
# Rendering + transport
# --------------------------------------------------------------------------


def _summarise(alert: dict) -> dict:
    row = alert["hackathon"]
    return {
        "id": row.id,
        "title": row.title,
        "url": row.url,
        "deadline": row.deadline.isoformat() if row.deadline else None,
        "days_left": alert["days_left"],
        "kind": alert["kind"],
        "match_score": alert["match"]["score"],
        "bookmarked": alert["bookmarked"],
        "prize": format_inr(row.prize_inr) if row.prize_inr else "—",
    }


def _render_text(profile: Profile, alerts: list[dict]) -> str:
    lines = [f"Hi {profile.name}, deadlines are approaching:", ""]
    for alert in alerts:
        row = alert["hackathon"]
        when = "TODAY" if alert["days_left"] == 0 else f"in {alert['days_left']} day(s)"
        star = "* " if alert["bookmarked"] else ""
        lines.append(f"{star}{row.title}")
        lines.append(
            f"   closes {when} ({row.deadline})  |  match {alert['match']['score']}%"
            f"  |  prize {format_inr(row.prize_inr) if row.prize_inr else '—'}"
        )
        lines.append(f"   {row.url}")
        lines.append("")
    lines.append("— HackRadar")
    return "\n".join(lines)


def _send_email(to_address: str, subject: str, body: str) -> bool:
    message = EmailMessage()
    message["From"] = settings.SMTP_FROM or settings.SMTP_USER
    message["To"] = to_address
    message["Subject"] = subject
    message.set_content(body)

    try:
        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=20) as server:
            server.starttls()
            if settings.SMTP_USER:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.send_message(message)
        return True
    except Exception:
        log.exception("Email delivery failed")
        return False


def _send_telegram(chat_id: str, body: str) -> bool:
    url = f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = httpx.post(
            url,
            json={"chat_id": chat_id, "text": body, "disable_web_page_preview": True},
            timeout=20,
        )
        resp.raise_for_status()
        return True
    except Exception:
        log.exception("Telegram delivery failed")
        return False
