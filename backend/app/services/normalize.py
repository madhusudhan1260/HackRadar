"""Turn messy scraped strings into typed, comparable fields.

Every collector emits a loose dict; this module is what makes rows from
Devpost, MLH and Unstop actually comparable to each other.
"""
from __future__ import annotations

import re
import unicodedata
from datetime import date, datetime
from typing import Any

from ..config import settings

# --------------------------------------------------------------------------
# Text helpers
# --------------------------------------------------------------------------

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")

# Words that add noise to a title when fingerprinting for duplicates.
_STOPWORDS = {
    "hackathon", "hack", "challenge", "contest", "competition", "the", "a", "an",
    "2024", "2025", "2026", "2027", "edition", "season", "online", "global",
    "international", "national", "series", "presents", "by",
}


def strip_html(value: str | None) -> str:
    if not value:
        return ""
    text = _TAG_RE.sub(" ", value)
    text = (
        text.replace("&amp;", "&")
        .replace("&nbsp;", " ")
        .replace("&#39;", "'")
        .replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
    )
    return _WS_RE.sub(" ", text).strip()


def slugify(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    return _NON_ALNUM.sub("-", value).strip("-")


def cluster_key(title: str) -> str:
    """Fingerprint used to spot the same event listed on several platforms."""
    words = [w for w in slugify(title).split("-") if w and w not in _STOPWORDS]
    return "-".join(sorted(set(words)))[:200]


# --------------------------------------------------------------------------
# Dates
# --------------------------------------------------------------------------

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%d %H:%M:%S",
)


def parse_date(value: Any) -> date | None:
    """Best-effort date parsing across the formats these platforms emit."""
    if value in (None, "", "TBD"):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()

    # ISO-8601 with timezone, e.g. 2026-08-15T23:59:00-07:00
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except ValueError:
        pass

    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue

    # Free text like "Aug 15, 2026" buried in a sentence, or "15 Aug 2026".
    m = re.search(
        r"(\d{1,2})\s+([A-Za-z]{3,9})\.?,?\s+(\d{4})|([A-Za-z]{3,9})\.?\s+(\d{1,2}),?\s+(\d{4})",
        text,
    )
    if m:
        candidate = m.group(0).replace(".", "").replace(",", "")
        for fmt in ("%d %b %Y", "%d %B %Y", "%b %d %Y", "%B %d %Y"):
            try:
                return datetime.strptime(candidate, fmt).date()
            except ValueError:
                continue
    return None


# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------

_CURRENCY_HINTS = {
    "₹": "INR", "rs.": "INR", "rs": "INR", "inr": "INR", "rupees": "INR",
    "$": "USD", "usd": "USD", "us$": "USD", "dollars": "USD",
    "€": "EUR", "eur": "EUR",
    "£": "GBP", "gbp": "GBP",
}

_MULTIPLIERS = {
    "k": 1_000, "thousand": 1_000,
    "l": 100_000, "lac": 100_000, "lakh": 100_000, "lakhs": 100_000,
    "m": 1_000_000, "mn": 1_000_000, "million": 1_000_000,
    "cr": 10_000_000, "crore": 10_000_000, "crores": 10_000_000,
}

_AMOUNT_RE = re.compile(
    r"(?P<sym>₹|\$|€|£|rs\.?|inr|usd|us\$|eur|gbp)?\s*"
    r"(?P<num>\d[\d,]*(?:\.\d+)?)\s*"
    r"(?P<mult>k|thousand|lakhs?|lacs?|l\b|crores?|cr\b|million|mn\b|m\b)?",
    re.IGNORECASE,
)


def parse_prize_inr(text: str | None, default_currency: str = "USD") -> int:
    """Extract the largest money amount from free text and convert to INR.

    "$8,000" -> 704000, "₹1.5 Lakh" -> 150000, "Prizes worth 50K" -> 50000.
    Returns 0 when no amount can be found.
    """
    if not text:
        return 0
    lowered = str(text).lower()
    if any(w in lowered for w in ("tbd", "to be announced", "no cash")):
        return 0

    best = 0
    for m in _AMOUNT_RE.finditer(lowered):
        raw_num = m.group("num")
        if not raw_num:
            continue
        try:
            amount = float(raw_num.replace(",", ""))
        except ValueError:
            continue
        if amount == 0:
            continue

        mult = (m.group("mult") or "").strip().lower()
        amount *= _MULTIPLIERS.get(mult, 1)

        sym = (m.group("sym") or "").strip().lower()
        currency = _CURRENCY_HINTS.get(sym)
        if currency is None:
            # No symbol on this match — fall back to any currency word nearby.
            currency = _detect_currency(lowered, default_currency)

        inr = amount * settings.FX_TO_INR.get(currency, 1.0)
        best = max(best, int(inr))

    return best


def _detect_currency(text: str, fallback: str) -> str:
    for hint, currency in _CURRENCY_HINTS.items():
        if hint in text:
            return currency
    return fallback


_FEE_RE = re.compile(r"(fee|entry|registration|ticket)[^.\n]{0,40}?(₹|rs\.?|inr|\$)\s*(\d[\d,]*)", re.I)


def parse_fee(text: str | None) -> tuple[bool, int]:
    """Return (is_free, fee_in_inr)."""
    if not text:
        return True, 0
    lowered = text.lower()
    if any(p in lowered for p in ("free entry", "free to participate", "no entry fee", "free registration")):
        return True, 0
    m = _FEE_RE.search(lowered)
    if m:
        fee = parse_prize_inr(f"{m.group(2)}{m.group(3)}", default_currency="INR")
        return (fee == 0), fee
    if "paid" in lowered and "entry" in lowered:
        return False, 0
    return True, 0


# --------------------------------------------------------------------------
# Place
# --------------------------------------------------------------------------

_INDIA_CITIES = {
    "india", "bharat", "bangalore", "bengaluru", "mumbai", "delhi", "new delhi",
    "hyderabad", "chennai", "kolkata", "pune", "ahmedabad", "jaipur", "noida",
    "gurgaon", "gurugram", "kochi", "coimbatore", "indore", "bhopal", "chandigarh",
    "lucknow", "nagpur", "vizag", "visakhapatnam", "surat", "vellore", "kanpur",
    "kharagpur", "roorkee", "guwahati", "trivandrum", "thiruvananthapuram",
    "mysore", "mysuru", "manipal", "warangal", "tiruchirappalli", "trichy",
}

_ONLINE_WORDS = ("online", "virtual", "remote", "anywhere", "worldwide", "digital")
_HYBRID_WORDS = ("hybrid", "online and offline", "in-person and online")


def parse_mode(*values: str | None) -> str:
    blob = " ".join(v for v in values if v).lower()
    if any(w in blob for w in _HYBRID_WORDS):
        return "hybrid"
    if any(w in blob for w in _ONLINE_WORDS):
        return "online"
    if blob.strip():
        return "offline"
    return "online"


def detect_india(*values: str | None) -> bool:
    blob = " ".join(v for v in values if v).lower()
    return any(re.search(rf"\b{re.escape(city)}\b", blob) for city in _INDIA_CITIES)


def parse_country(location: str | None) -> str:
    if not location:
        return ""
    if detect_india(location):
        return "India"
    parts = [p.strip() for p in location.split(",") if p.strip()]
    return parts[-1] if parts else ""


# --------------------------------------------------------------------------
# Team size
# --------------------------------------------------------------------------

_TEAM_RE = re.compile(r"team[^.\n]{0,30}?(\d+)\s*(?:-|to|–)\s*(\d+)", re.I)
_TEAM_MAX_RE = re.compile(r"(?:up to|max(?:imum)?(?: of)?)\s*(\d+)\s*(?:members|people|participants)", re.I)
_SOLO_RE = re.compile(r"\b(solo|individual)\s*(?:only|participation)\b", re.I)


def parse_team_size(text: str | None) -> tuple[int, int]:
    if not text:
        return 1, 4
    if _SOLO_RE.search(text):
        return 1, 1
    m = _TEAM_RE.search(text)
    if m:
        lo, hi = int(m.group(1)), int(m.group(2))
        if 1 <= lo <= hi <= 20:
            return lo, hi
    m = _TEAM_MAX_RE.search(text)
    if m:
        hi = int(m.group(1))
        if 1 <= hi <= 20:
            return 1, hi
    return 1, 4


_STUDENT_RE = re.compile(
    r"\b(student|students only|college|university|undergrad|campus|school|"
    r"b\.?tech|freshers?)\b",
    re.I,
)


def detect_student_only(*values: str | None) -> bool:
    blob = " ".join(v for v in values if v)
    return bool(_STUDENT_RE.search(blob))
