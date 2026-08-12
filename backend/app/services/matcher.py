"""Skill-based match scoring — the "95% Match / Requires Blockchain" feature.

The score is deliberately explainable: every point is attributable to a
reason we can show the user, rather than an opaque embedding distance.

    skills fit      50 pts   your stack vs the event's tech tags
    interest fit    30 pts   your interests vs the event's categories
    preference fit  20 pts   mode / location / prize / fee / team size
"""
from __future__ import annotations

from datetime import date
from typing import Iterable

from .classifier import CATEGORIES, TECH_TAGS

# Interest words -> canonical categories, so a profile saying "AI" matches
# a hackathon classified as "ai-ml".
_INTEREST_ALIASES: dict[str, str] = {
    "ai": "ai-ml", "ml": "ai-ml", "machine learning": "ai-ml", "ai/ml": "ai-ml",
    "deep learning": "ai-ml", "data science": "ai-ml", "genai": "ai-ml", "llm": "ai-ml",
    "web": "web", "web development": "web", "webdev": "web", "frontend": "web",
    "backend": "web", "full stack": "web", "fullstack": "web",
    "cyber": "cybersecurity", "security": "cybersecurity", "cybersecurity": "cybersecurity",
    "ctf": "cybersecurity", "infosec": "cybersecurity",
    "cloud": "cloud", "devops": "cloud", "aws": "cloud", "azure": "cloud", "gcp": "cloud",
    "blockchain": "blockchain", "web3": "blockchain", "crypto": "blockchain",
    "mobile": "mobile", "android": "mobile", "ios": "mobile", "app development": "mobile",
    "data": "data", "analytics": "data", "data analytics": "data",
    "iot": "iot-hardware", "hardware": "iot-hardware", "embedded": "iot-hardware",
    "robotics": "iot-hardware", "vlsi": "iot-hardware",
    "fintech": "fintech", "finance": "fintech", "quant": "fintech",
    "health": "healthtech", "healthcare": "healthtech", "medtech": "healthtech",
    "game": "gamedev", "gamedev": "gamedev", "game development": "gamedev", "ar/vr": "gamedev",
    "design": "design", "ui/ux": "design", "ux": "design",
    "climate": "sustainability", "sustainability": "sustainability",
    "open source": "open-source", "oss": "open-source",
}

# Near-interchangeable skills. If you already have one member of a family,
# the others are not reported as gaps — knowing Machine Learning but not
# having ticked "AI" is not a real gap worth warning about.
_SKILL_FAMILIES: list[set[str]] = [
    {"AI", "Machine Learning", "Deep Learning", "LLM", "NLP", "Computer Vision", "Data Science"},
    {"JavaScript", "TypeScript", "React", "HTML/CSS"},
    {"AWS", "Azure", "GCP", "Docker", "Kubernetes"},
    {"Android", "iOS", "Flutter"},
]

# Category -> the tech tags it typically demands. Used to warn about gaps
# ("Requires Blockchain") when the user has no matching skill.
_CATEGORY_CORE_SKILLS: dict[str, list[str]] = {
    "ai-ml": ["Machine Learning", "Deep Learning", "Python", "LLM", "NLP", "Computer Vision"],
    "web": ["JavaScript", "React", "HTML/CSS", "TypeScript", "Python"],
    "cybersecurity": ["Cybersecurity", "Python", "C++"],
    "cloud": ["AWS", "Azure", "GCP", "Docker", "Kubernetes"],
    "blockchain": ["Blockchain", "Solidity"],
    "mobile": ["Android", "iOS", "Flutter"],
    "data": ["SQL", "Python"],
    "iot-hardware": ["IoT", "C++", "Python"],
    "gamedev": ["Game Development", "C++"],
    "design": ["UI/UX"],
}


def canonical_skill(raw: str) -> str:
    """Map a free-text skill to a canonical tag label ('flask' -> 'Python')."""
    s = (raw or "").strip().lower()
    if not s:
        return ""
    for label, aliases in TECH_TAGS.items():
        if s == label.lower() or any(s == a.strip().lower() for a in aliases):
            return label
    for label, aliases in TECH_TAGS.items():
        if any(a.strip().lower() in s or s in a.strip().lower() for a in aliases if len(a) > 2):
            return label
    return raw.strip().title()


def canonical_interest(raw: str) -> str:
    s = (raw or "").strip().lower()
    if s in _INTEREST_ALIASES:
        return _INTEREST_ALIASES[s]
    if s in CATEGORIES:
        return s
    for alias, cat in _INTEREST_ALIASES.items():
        if alias in s:
            return cat
    return s


def _norm_set(values: Iterable[str], fn) -> set[str]:
    return {v for v in (fn(x) for x in values or []) if v}


def score(hackathon, profile, today: date | None = None) -> dict:
    """Return {score, level, reasons, missing} for one hackathon/profile pair."""
    today = today or date.today()

    my_skills = _norm_set(profile.skills, canonical_skill)
    my_interests = _norm_set(profile.interests, canonical_interest)
    event_tags = _norm_set(hackathon.tags or [], canonical_skill)
    event_cats = set(hackathon.categories or [])

    reasons: list[str] = []
    missing: list[str] = []

    # --- 1. Skills (50) -------------------------------------------------
    if event_tags:
        overlap = my_skills & event_tags
        skill_pts = 50 * len(overlap) / len(event_tags)
        # Cap the penalty for very broad listings: matching 3 of 10 tags is fine.
        skill_pts = max(skill_pts, 50 * min(len(overlap), 3) / 3 * 0.8) if overlap else 0.0
        if overlap:
            reasons.append("Matches your " + ", ".join(sorted(overlap)[:4]))
        missing.extend(_real_gaps(event_tags - my_skills, my_skills)[:3])
    else:
        # No tags extracted — stay neutral rather than punishing the listing.
        skill_pts = 25.0

    # --- 2. Interests (30) ----------------------------------------------
    # One matching interest already means the event is relevant; a second
    # adds confidence. Requiring two would punish narrowly-tagged events.
    if event_cats and my_interests:
        cat_overlap = my_interests & event_cats
        interest_pts = (20.0 if cat_overlap else 0.0) + (10.0 if len(cat_overlap) >= 2 else 0.0)
        if cat_overlap:
            reasons.append("In your interest area: " + ", ".join(sorted(cat_overlap)))
    elif not my_interests:
        interest_pts = 15.0
    else:
        interest_pts = 0.0

    # --- 3. Preferences (20) --------------------------------------------
    pref_pts = 0.0
    if profile.prefer_mode in ("any", "") or hackathon.mode == profile.prefer_mode or hackathon.mode == "hybrid":
        pref_pts += 5
    else:
        missing.append(f"{hackathon.mode} only")

    if not profile.india_only or hackathon.is_india or hackathon.mode == "online":
        pref_pts += 4
    else:
        missing.append("outside India")

    if hackathon.prize_inr >= profile.min_prize_inr:
        pref_pts += 4
        if hackathon.prize_inr >= 100_000:
            reasons.append(f"Big prize pool ({format_inr(hackathon.prize_inr)})")
    if hackathon.is_free or not profile.free_only:
        pref_pts += 3
    else:
        missing.append("paid entry")

    team_size = max(1, profile.team_size or 1)
    if hackathon.team_min <= team_size <= hackathon.team_max:
        pref_pts += 4
        reasons.append(f"Fits your team of {team_size}")
    else:
        missing.append(f"team of {hackathon.team_min}-{hackathon.team_max}")

    total = skill_pts + interest_pts + pref_pts

    # --- Hard blockers: a required core skill the user simply lacks ------
    for cat in event_cats:
        core = _CATEGORY_CORE_SKILLS.get(cat, [])
        if core and not (my_skills & set(core)):
            total *= 0.55
            missing.insert(0, f"Requires {core[0]}")
            break

    # Deadline already gone -> not actionable.
    if hackathon.deadline and hackathon.deadline < today:
        total *= 0.2
        missing.append("deadline passed")

    final = int(max(0, min(100, round(total))))
    return {
        "score": final,
        "level": _level(final),
        "reasons": reasons[:4],
        "missing": _dedupe(missing)[:3],
    }


def _real_gaps(gaps: set[str], my_skills: set[str]) -> list[str]:
    """Drop gaps that a skill you already have effectively covers."""
    covered: set[str] = set()
    for family in _SKILL_FAMILIES:
        if my_skills & family:
            covered |= family
    return sorted(gaps - covered)


def _level(value: int) -> str:
    if value >= 80:
        return "strong"
    if value >= 60:
        return "good"
    if value >= 40:
        return "stretch"
    return "weak"


def _dedupe(items: list[str]) -> list[str]:
    seen, out = set(), []
    for item in items:
        # "Requires Blockchain" and a bare "Blockchain" gap are the same fact.
        key = item.lower().removeprefix("requires ")
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out


def format_inr(amount: int) -> str:
    if amount >= 10_000_000:
        return f"₹{amount / 10_000_000:.1f}Cr".replace(".0", "")
    if amount >= 100_000:
        return f"₹{amount / 100_000:.1f}L".replace(".0", "")
    if amount >= 1_000:
        return f"₹{amount / 1_000:.0f}K"
    return f"₹{amount}"
