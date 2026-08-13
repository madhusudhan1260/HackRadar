"""Application configuration, loaded from environment variables / .env."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _normalize_db_url(url: str) -> str:
    """Make hosted Postgres URLs work with SQLAlchemy 2.

    Render, Heroku and Railway all hand out `postgres://…`, a scheme
    SQLAlchemy 2 dropped. Rewrite it to the psycopg 3 driver, which is what
    requirements.txt installs.
    """
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://") :]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://") :]
    return url


class Settings:
    # --- Database -------------------------------------------------------
    # SQLite by default so the project runs with zero setup.
    # Point DATABASE_URL at Postgres for production, e.g.
    #   postgresql+psycopg://user:pass@localhost:5432/hackradar
    DATABASE_URL: str = _normalize_db_url(
        os.getenv("DATABASE_URL", f"sqlite:///{BASE_DIR / 'hackradar.db'}")
    )

    # --- Collectors -----------------------------------------------------
    # Comma separated list of collector names to run. See app/collectors.
    # Real sources only by default. The 'seed' collector is bundled sample
    # data whose links point at example.com — fine for offline development
    # and tests, never for a site anyone will actually click through.
    ENABLED_COLLECTORS: list[str] = [
        c.strip()
        for c in os.getenv("ENABLED_COLLECTORS", "devpost,mlh").split(",")
        if c.strip()
    ]
    HTTP_TIMEOUT: float = float(os.getenv("HTTP_TIMEOUT", "20"))
    USER_AGENT: str = os.getenv(
        "USER_AGENT",
        "HackRadar/1.0 (+https://github.com/yourname/hackathon-hub) hackathon aggregator",
    )
    # How often the background scheduler re-runs ingestion.
    INGEST_INTERVAL_MINUTES: int = int(os.getenv("INGEST_INTERVAL_MINUTES", "360"))
    RUN_SCHEDULER: bool = os.getenv("RUN_SCHEDULER", "true").lower() == "true"

    # --- Money ----------------------------------------------------------
    # Static conversion rates -> INR. Good enough for bucketing/filtering;
    # swap for a live FX API if you ever need accuracy.
    FX_TO_INR: dict[str, float] = {
        "INR": 1.0,
        "USD": 88.0,
        "EUR": 96.0,
        "GBP": 112.0,
    }

    # --- Email (verification codes) --------------------------------------
    # Leave EMAIL_PROVIDER blank to auto-select: brevo -> resend -> smtp ->
    # console. Prefer an HTTP API in production: many hosts, including
    # Render's free tier, block outbound SMTP ports.
    EMAIL_PROVIDER: str = os.getenv("EMAIL_PROVIDER", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "HackRadar")
    BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
    RESEND_API_KEY: str = os.getenv("RESEND_API_KEY", "")

    # --- Notifications --------------------------------------------------
    SMTP_HOST: str = os.getenv("SMTP_HOST", "")
    SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER: str = os.getenv("SMTP_USER", "")
    SMTP_PASSWORD: str = os.getenv("SMTP_PASSWORD", "")
    SMTP_FROM: str = os.getenv("SMTP_FROM", os.getenv("SMTP_USER", ""))
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHAT_ID: str = os.getenv("TELEGRAM_CHAT_ID", "")

    # --- Optional LLM enrichment ---------------------------------------
    # If set, hackathon descriptions get classified/summarised by Claude.
    # Everything works without it — the rule-based classifier is the default.
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    ANTHROPIC_MODEL: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5")

    # --- Auth -----------------------------------------------------------
    # Used to pepper OTP hashes and sign nothing else — session tokens are
    # random and stored hashed. Change it and all live sessions/OTPs die.
    SECRET_KEY: str = os.getenv("SECRET_KEY", "dev-secret-change-me-in-production")
    SESSION_TTL_HOURS: int = int(os.getenv("SESSION_TTL_HOURS", "168"))  # 7 days
    MIN_PASSWORD_LENGTH: int = int(os.getenv("MIN_PASSWORD_LENGTH", "8"))

    # --- Support ---------------------------------------------------------
    # Shown on the "forgot password" screen. Password resets are handled by
    # the admin rather than automatically.
    SUPPORT_EMAIL: str = os.getenv("SUPPORT_EMAIL", "madhuusudhann01@gmail.com")

    # --- OTP (retained for the notifier; registration no longer uses it) --
    OTP_LENGTH: int = int(os.getenv("OTP_LENGTH", "6"))
    OTP_TTL_MINUTES: int = int(os.getenv("OTP_TTL_MINUTES", "5"))
    OTP_MAX_ATTEMPTS: int = int(os.getenv("OTP_MAX_ATTEMPTS", "5"))
    OTP_RESEND_COOLDOWN_SECONDS: int = int(os.getenv("OTP_RESEND_COOLDOWN_SECONDS", "60"))
    # Max OTPs per phone number per hour — SMS costs money and OTP
    # endpoints are a favourite target for abuse.
    OTP_HOURLY_LIMIT: int = int(os.getenv("OTP_HOURLY_LIMIT", "5"))

    # --- SMS delivery ----------------------------------------------------
    # console = print the OTP to the server log (development only).
    # twilio / msg91 = real SMS, needs the credentials below.
    SMS_PROVIDER: str = os.getenv("SMS_PROVIDER", "console").lower()
    DEFAULT_COUNTRY_CODE: str = os.getenv("DEFAULT_COUNTRY_CODE", "+91")

    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_FROM_NUMBER: str = os.getenv("TWILIO_FROM_NUMBER", "")

    MSG91_AUTH_KEY: str = os.getenv("MSG91_AUTH_KEY", "")
    MSG91_SENDER_ID: str = os.getenv("MSG91_SENDER_ID", "HCKRDR")
    MSG91_TEMPLATE_ID: str = os.getenv("MSG91_TEMPLATE_ID", "")

    # --- First admin ------------------------------------------------------
    # Optional convenience bootstrap. Prefer scripts/manage.py create-admin,
    # which prompts for the password instead of leaving it in a file.
    ADMIN_USERNAME: str = os.getenv("ADMIN_USERNAME", "")
    ADMIN_PASSWORD: str = os.getenv("ADMIN_PASSWORD", "")
    ADMIN_NAME: str = os.getenv("ADMIN_NAME", "Administrator")
    ADMIN_PHONE: str = os.getenv("ADMIN_PHONE", "")

    CORS_ORIGINS: list[str] = [
        o.strip()
        for o in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if o.strip()
    ]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
