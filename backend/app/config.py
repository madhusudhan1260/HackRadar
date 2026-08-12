"""Application configuration, loaded from environment variables / .env."""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


class Settings:
    # --- Database -------------------------------------------------------
    # SQLite by default so the project runs with zero setup.
    # Point DATABASE_URL at Postgres for production, e.g.
    #   postgresql+psycopg://user:pass@localhost:5432/hackradar
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", f"sqlite:///{BASE_DIR / 'hackradar.db'}"
    )

    # --- Collectors -----------------------------------------------------
    # Comma separated list of collector names to run. See app/collectors.
    ENABLED_COLLECTORS: list[str] = [
        c.strip()
        for c in os.getenv("ENABLED_COLLECTORS", "seed,devpost,mlh").split(",")
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
