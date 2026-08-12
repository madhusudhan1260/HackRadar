"""Database models.

The core table is `hackathons`. One row = one listing on one platform.
The same event often appears on several platforms, so rows also carry a
`cluster_key` (a normalised title fingerprint) that lets the API collapse
mirrors into a single card and report "also on Devpost, Unstop".
"""
from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Hackathon(Base):
    __tablename__ = "hackathons"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_hackathon_source"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    # --- provenance -----------------------------------------------------
    source: Mapped[str] = mapped_column(String(40), index=True)
    source_id: Mapped[str] = mapped_column(String(200))
    url: Mapped[str] = mapped_column(String(600))
    cluster_key: Mapped[str] = mapped_column(String(200), index=True, default="")

    # --- content --------------------------------------------------------
    title: Mapped[str] = mapped_column(String(400), index=True)
    description: Mapped[str] = mapped_column(Text, default="")
    organizer: Mapped[str] = mapped_column(String(240), default="")
    image_url: Mapped[str] = mapped_column(String(600), default="")

    # --- dates ----------------------------------------------------------
    deadline: Mapped[date | None] = mapped_column(Date, index=True, nullable=True)
    start_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    # --- place ----------------------------------------------------------
    mode: Mapped[str] = mapped_column(String(20), default="online")  # online|offline|hybrid
    location: Mapped[str] = mapped_column(String(240), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    is_india: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # --- money ----------------------------------------------------------
    prize_text: Mapped[str] = mapped_column(String(240), default="")
    prize_inr: Mapped[int] = mapped_column(Integer, default=0, index=True)
    is_free: Mapped[bool] = mapped_column(Boolean, default=True, index=True)
    fee_inr: Mapped[int] = mapped_column(Integer, default=0)

    # --- team / audience -------------------------------------------------
    team_min: Mapped[int] = mapped_column(Integer, default=1)
    team_max: Mapped[int] = mapped_column(Integer, default=4)
    is_student_only: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    # --- classification --------------------------------------------------
    categories: Mapped[list[str]] = mapped_column(JSON, default=list)
    tags: Mapped[list[str]] = mapped_column(JSON, default=list)

    # --- housekeeping ----------------------------------------------------
    status: Mapped[str] = mapped_column(String(20), default="open")  # open|closed
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )
    raw: Mapped[dict] = mapped_column(JSON, default=dict)

    bookmarks: Mapped[list["Bookmark"]] = relationship(
        back_populates="hackathon", cascade="all, delete-orphan"
    )


class Profile(Base):
    """The user's skill profile. Drives the AI match score."""

    __tablename__ = "profiles"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), default="Me")
    email: Mapped[str] = mapped_column(String(240), default="")
    skills: Mapped[list[str]] = mapped_column(JSON, default=list)
    interests: Mapped[list[str]] = mapped_column(JSON, default=list)

    # preference weights used when ranking
    prefer_mode: Mapped[str] = mapped_column(String(20), default="any")  # any|online|offline
    india_only: Mapped[bool] = mapped_column(Boolean, default=False)
    min_prize_inr: Mapped[int] = mapped_column(Integer, default=0)
    free_only: Mapped[bool] = mapped_column(Boolean, default=False)
    team_size: Mapped[int] = mapped_column(Integer, default=1)

    # notifications
    notify_days_before: Mapped[list[int]] = mapped_column(JSON, default=lambda: [7, 3, 1])
    notify_min_score: Mapped[int] = mapped_column(Integer, default=60)
    telegram_chat_id: Mapped[str] = mapped_column(String(80), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, default=utcnow, onupdate=utcnow
    )


class Bookmark(Base):
    __tablename__ = "bookmarks"
    __table_args__ = (
        UniqueConstraint("profile_id", "hackathon_id", name="uq_bookmark"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    hackathon_id: Mapped[int] = mapped_column(
        ForeignKey("hackathons.id", ondelete="CASCADE"), index=True
    )
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)

    hackathon: Mapped[Hackathon] = relationship(back_populates="bookmarks")


class NotificationLog(Base):
    """Remembers what we already alerted about, so nothing fires twice."""

    __tablename__ = "notification_log"
    __table_args__ = (
        UniqueConstraint(
            "profile_id", "hackathon_id", "kind", name="uq_notification"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    profile_id: Mapped[int] = mapped_column(ForeignKey("profiles.id"), index=True)
    hackathon_id: Mapped[int] = mapped_column(ForeignKey("hackathons.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))  # e.g. "deadline-3d"
    channel: Mapped[str] = mapped_column(String(20), default="email")
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)


class IngestRun(Base):
    """One row per collector run — useful for the /health and admin views."""

    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(40), index=True)
    started_at: Mapped[datetime] = mapped_column(DateTime, default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    fetched: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    updated: Mapped[int] = mapped_column(Integer, default=0)
    ok: Mapped[bool] = mapped_column(Boolean, default=True)
    error: Mapped[str] = mapped_column(Text, default="")
