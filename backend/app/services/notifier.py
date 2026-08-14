"""Deadline notifications over email and Telegram.

`pending_alerts` decides *what* should fire (and is safe to call any time —
it never sends). `dispatch` actually sends and records the send so the same
alert never goes out twice.

Email goes through services/mailer.py — the same Brevo/Resend/SMTP/console
dispatcher OTPs use. It used to have its own raw smtplib sender pointed at
SMTP_HOST directly, which meant it silently broke wherever OTP delivery
broke (Render blocks outbound SMTP), just discovered later since nothing
exercises this path until a deadline is actually close.
"""
from __future__ import annotations

import logging
from datetime import date

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import settings
from ..models import Bookmark, Hackathon, NotificationLog, Profile
from . import mailer
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


def _destination_email(db: Session, profile: Profile) -> str:
    """Where deadline mail goes.

    Profile.email is an old, separately-editable field predating account
    email/OTP; most users never touch it. Falling back to the verified
    login email means notifications work out of the box for every
    registered account, not only ones who filled in a second address.
    """
    if profile.email and profile.email.strip():
        return profile.email.strip()
    if profile.user_id:
        from ..models import User

        user = db.get(User, profile.user_id)
        if user and user.email:
            return user.email
    return ""


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

    destination = _destination_email(db, profile)
    if destination:
        result = mailer.send(
            destination,
            f"{len(alerts)} hackathon deadline{'s' if len(alerts) != 1 else ''} coming up",
            body_text,
            _render_html(profile, alerts),
        )
        if result.delivered:
            channels.append("email")
        else:
            log.warning("Deadline email to profile %s failed: %s", profile.id, result.note)

    chat_id = profile.telegram_chat_id or settings.TELEGRAM_CHAT_ID
    if settings.TELEGRAM_BOT_TOKEN and chat_id:
        if _send_telegram(chat_id, body_text):
            channels.append("telegram")

    if not channels:
        return {
            "sent": 0,
            "channels": [],
            "alerts": summary,
            "note": (
                "No delivery channel reachable. Add an email to your profile, or "
                "set TELEGRAM_* — alerts still show here in the meantime."
            ),
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


def _render_html(profile: Profile, alerts: list[dict]) -> str:
    rows_html = ""
    for alert in alerts:
        row = alert["hackathon"]
        when = "closes today" if alert["days_left"] == 0 else f"closes in {alert['days_left']} day(s)"
        badge = "⭐ Saved · " if alert["bookmarked"] else ""
        prize = format_inr(row.prize_inr) if row.prize_inr else "—"
        rows_html += f"""
        <tr>
          <td style="padding:14px 0;border-bottom:1px solid #1f2a3d;">
            <div style="font-size:14px;font-weight:650;color:#e8edf5;">{row.title}</div>
            <div style="font-size:12.5px;color:#94a3b8;margin-top:3px;">
              {badge}{when} · match {alert['match']['score']}% · prize {prize}
            </div>
            <a href="{row.url}" style="font-size:12.5px;color:#a5b4fc;">View / apply →</a>
          </td>
        </tr>"""

    return f"""\
<!doctype html>
<html>
  <body style="margin:0;padding:24px;background:#0a0e17;font-family:-apple-system,
               BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;color:#e8edf5;">
    <div style="max-width:480px;margin:0 auto;background:#111827;border:1px solid #1f2a3d;
                border-radius:16px;padding:28px;">
      <h1 style="margin:0 0 4px;font-size:19px;">📡 HackRadar</h1>
      <p style="margin:0 0 20px;color:#64748b;font-size:13px;">
        {len(alerts)} deadline{'s' if len(alerts) != 1 else ''} coming up, {profile.name}
      </p>
      <table style="width:100%;border-collapse:collapse;">
        {rows_html}
      </table>
      <p style="margin:20px 0 0;color:#64748b;font-size:11.5px;">
        You're getting this because these are saved or match your profile well.
        Adjust alert timing under Profile in HackRadar.
      </p>
    </div>
  </body>
</html>"""


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
