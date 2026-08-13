"""Pydantic request/response models."""
from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field


class MatchInfo(BaseModel):
    score: int
    level: str
    reasons: list[str] = []
    missing: list[str] = []


class Mirror(BaseModel):
    source: str
    url: str


class HackathonOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    url: str
    title: str
    description: str = ""
    organizer: str = ""
    image_url: str = ""

    deadline: date | None = None
    start_date: date | None = None
    end_date: date | None = None
    days_left: int | None = None

    mode: str
    location: str = ""
    country: str = ""
    is_india: bool

    prize_text: str = ""
    prize_inr: int = 0
    prize_display: str = "—"
    is_free: bool = True
    fee_inr: int = 0

    team_min: int = 1
    team_max: int = 4
    is_student_only: bool = False

    categories: list[str] = []
    tags: list[str] = []
    status: str = "open"

    bookmarked: bool = False
    match: MatchInfo | None = None
    also_on: list[Mirror] = []


class HackathonList(BaseModel):
    total: int
    page: int
    per_page: int
    items: list[HackathonOut]


class DeadlineGroup(BaseModel):
    label: str
    items: list[HackathonOut]


class DeadlineBoard(BaseModel):
    groups: list[DeadlineGroup]
    generated_on: date


class ProfileIn(BaseModel):
    name: str | None = None
    email: str | None = None
    skills: list[str] | None = None
    interests: list[str] | None = None
    prefer_mode: str | None = Field(default=None, pattern="^(any|online|offline|hybrid)$")
    india_only: bool | None = None
    min_prize_inr: int | None = Field(default=None, ge=0)
    free_only: bool | None = None
    team_size: int | None = Field(default=None, ge=1, le=20)
    notify_days_before: list[int] | None = None
    notify_min_score: int | None = Field(default=None, ge=0, le=100)
    telegram_chat_id: str | None = None


class ProfileOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    email: str = ""
    skills: list[str] = []
    interests: list[str] = []
    prefer_mode: str = "any"
    india_only: bool = False
    min_prize_inr: int = 0
    free_only: bool = False
    team_size: int = 1
    notify_days_before: list[int] = []
    notify_min_score: int = 60
    telegram_chat_id: str = ""
    updated_at: datetime | None = None


# --------------------------------------------------------------------------
# Auth
# --------------------------------------------------------------------------


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    username: str = Field(min_length=3, max_length=30)
    email: str = Field(min_length=5, max_length=240)
    phone: str = Field(min_length=8, max_length=20)
    password: str = Field(min_length=6, max_length=200)


class OtpSentOut(BaseModel):
    """A code has been sent. Never carries the code itself in production."""

    sent: bool
    #: Masked destination the code went to, e.g. 'mad•••••@gmail.com'.
    sent_to_masked: str
    expires_in: int
    resend_in: int
    note: str = ""
    #: Populated only by the console SMS provider, so the flow is testable
    #: locally without a gateway. Always null once a real provider is set.
    dev_code: str | None = None
    #: Shown as a fallback route when SMS cannot be delivered.
    support_email: str = ""


class VerifyOtpIn(BaseModel):
    username: str
    code: str = Field(min_length=4, max_length=10)


class ResetPasswordIn(BaseModel):
    username: str
    code: str = Field(min_length=4, max_length=10)
    new_password: str = Field(min_length=6, max_length=200)


class SupportInfoOut(BaseModel):
    """Fallback for forgot-password when no SMS channel can be reached."""

    support_email: str
    message: str


class AdminResetPasswordIn(BaseModel):
    new_password: str = Field(min_length=6, max_length=200)


class LoginIn(BaseModel):
    username: str
    password: str
    #: Set by the Admin tab on the login page. A non-admin account that
    #: authenticates here is refused rather than silently signed in.
    as_admin: bool = False


class OtpLogOut(BaseModel):
    """Admin view of OTP delivery — never includes the code itself."""

    id: int
    username: str = ""
    name: str = ""
    sent_to: str = ""
    purpose: str
    delivered: bool
    delivery_note: str = ""
    attempts: int = 0
    consumed: bool = False
    expired: bool = False
    created_at: datetime


class ForgotStartIn(BaseModel):
    username: str


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    name: str
    email: str = ""
    phone_masked: str = ""
    role: str
    status: str
    phone_verified: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None
    login_count: int = 0


class AuthOut(BaseModel):
    token: str
    user: UserOut


class AdminUserOut(UserOut):
    """Admin view — full phone number and email, plus activity counters."""

    phone: str
    active_sessions: int = 0
    bookmarks: int = 0


class LoginEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int | None = None
    username_tried: str = ""
    name: str = ""
    phone: str = ""
    event: str
    success: bool
    reason: str = ""
    ip: str = ""
    created_at: datetime


class AdminOverviewOut(BaseModel):
    total_users: int
    active_users: int
    pending_users: int
    admins: int
    logins_today: int
    failed_logins_today: int
    sms: dict


class BookmarkIn(BaseModel):
    hackathon_id: int
    note: str = ""


class StatsOut(BaseModel):
    total: int
    open: int
    india: int
    online: int
    free: int
    student: int
    by_source: dict[str, int]
    by_category: dict[str, int]
    closing_this_week: int
    last_ingest: datetime | None = None


class IngestRequest(BaseModel):
    sources: list[str] | None = None
    limit: int = Field(default=200, ge=1, le=1000)


class IngestResult(BaseModel):
    source: str
    ok: bool
    fetched: int
    created: int
    updated: int
    error: str = ""


class SourceInfo(BaseModel):
    name: str
    access_note: str = ""
    enabled: bool
    last_run: datetime | None = None
    last_ok: bool | None = None
    count: int = 0
