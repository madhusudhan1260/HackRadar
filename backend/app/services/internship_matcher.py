"""Skill-based match scoring for internships.

A trimmed version of services/matcher.py: team size, entry fee and prize
floor don't apply to internships, so the 50/30/20 hackathon split becomes
skills 60 / interests 40, reusing the same canonical_skill/canonical_interest
vocabulary so a profile means the same thing in both places.
"""
from __future__ import annotations

from .matcher import canonical_interest, canonical_skill, format_inr  # noqa: F401 (re-exported)


def _norm_set(values, fn) -> set[str]:
    return {v for v in (fn(x) for x in values or []) if v}


def score(internship, profile) -> dict:
    my_skills = _norm_set(profile.skills, canonical_skill)
    my_interests = _norm_set(profile.interests, canonical_interest)
    posting_tags = _norm_set(internship.tags or [], canonical_skill)
    posting_cats = set(internship.categories or [])

    reasons: list[str] = []
    missing: list[str] = []

    if posting_tags:
        overlap = my_skills & posting_tags
        skill_pts = 60 * len(overlap) / len(posting_tags)
        skill_pts = max(skill_pts, 60 * min(len(overlap), 3) / 3 * 0.8) if overlap else 0.0
        if overlap:
            reasons.append("Matches your " + ", ".join(sorted(overlap)[:4]))
        missing.extend(sorted(posting_tags - my_skills)[:3])
    else:
        skill_pts = 30.0

    if posting_cats and my_interests:
        cat_overlap = my_interests & posting_cats
        interest_pts = (25.0 if cat_overlap else 0.0) + (15.0 if len(cat_overlap) >= 2 else 0.0)
        if cat_overlap:
            reasons.append("In your interest area: " + ", ".join(sorted(cat_overlap)))
    elif not my_interests:
        interest_pts = 20.0
    else:
        interest_pts = 0.0

    if internship.is_paid and internship.stipend_inr:
        reasons.append(f"Paid — {format_inr(internship.stipend_inr)}")

    total = int(max(0, min(100, round(skill_pts + interest_pts))))

    if internship.status != "open":
        total = int(total * 0.2)
        missing.append("closed")

    return {
        "score": total,
        "level": _level(total),
        "reasons": reasons[:4],
        "missing": missing[:3],
    }


def _level(value: int) -> str:
    if value >= 80:
        return "strong"
    if value >= 60:
        return "good"
    if value >= 40:
        return "stretch"
    return "weak"
