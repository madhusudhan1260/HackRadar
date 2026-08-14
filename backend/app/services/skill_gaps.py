"""What to learn next, ranked by how many hackathons it actually unlocks.

Not a static "learn these trending skills" list — every number here comes
from re-running the real match scorer with one candidate skill added to a
copy of the profile, so "would unlock 6 hackathons, +18 points average" is
a measured claim, not a guess.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from types import SimpleNamespace
from urllib.parse import quote

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Hackathon, Profile
from .classifier import TECH_TAGS
from .dedupe import collapse
from .matcher import canonical_skill, score as match_score

# A match at "good" or better is the bar for "worth applying to".
GOOD_THRESHOLD_LEVELS = {"good", "strong"}

# How many open events to scan, and how many of the most-requested gap
# skills to actually re-score against. Re-scoring is cheap (pure Python),
# but there is no reason to evaluate a skill that only ever appears once.
MAX_EVENTS_SCANNED = 250
MAX_CANDIDATES_EVALUATED = 14
TOP_RESULTS = 8

# Curated, stable links — never a fabricated or guessed URL. Anything not
# listed here falls back to a search query, which always resolves.
LEARNING_RESOURCES: dict[str, dict[str, str]] = {
    "Python": {"label": "Official Python tutorial", "url": "https://docs.python.org/3/tutorial/"},
    "JavaScript": {"label": "MDN JavaScript guide", "url": "https://developer.mozilla.org/en-US/docs/Web/JavaScript/Guide"},
    "TypeScript": {"label": "TypeScript handbook", "url": "https://www.typescriptlang.org/docs/handbook/intro.html"},
    "React": {"label": "React documentation", "url": "https://react.dev/learn"},
    "C++": {"label": "learncpp.com", "url": "https://www.learncpp.com/"},
    "Java": {"label": "Oracle Java tutorials", "url": "https://docs.oracle.com/javase/tutorial/"},
    "Go": {"label": "A Tour of Go", "url": "https://go.dev/tour/"},
    "Rust": {"label": "The Rust Book", "url": "https://doc.rust-lang.org/book/"},
    "SQL": {"label": "SQLBolt interactive lessons", "url": "https://sqlbolt.com/"},
    "HTML/CSS": {"label": "MDN web basics", "url": "https://developer.mozilla.org/en-US/docs/Learn"},
    "Machine Learning": {"label": "Google's ML crash course", "url": "https://developers.google.com/machine-learning/crash-course"},
    "Deep Learning": {"label": "fast.ai practical deep learning", "url": "https://course.fast.ai/"},
    "LLM": {"label": "Anthropic's prompt engineering guide", "url": "https://docs.claude.com/en/docs/build-with-claude/prompt-engineering/overview"},
    "NLP": {"label": "Hugging Face NLP course", "url": "https://huggingface.co/learn/nlp-course"},
    "Computer Vision": {"label": "OpenCV tutorials", "url": "https://docs.opencv.org/4.x/d9/df8/tutorial_root.html"},
    "AWS": {"label": "AWS free tier + skill builder", "url": "https://aws.amazon.com/free/"},
    "Azure": {"label": "Microsoft Learn: Azure fundamentals", "url": "https://learn.microsoft.com/en-us/training/azure/"},
    "GCP": {"label": "Google Cloud Skills Boost", "url": "https://www.cloudskillsboost.google/"},
    "Docker": {"label": "Docker's official get-started guide", "url": "https://docs.docker.com/get-started/"},
    "Kubernetes": {"label": "Kubernetes basics tutorial", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/"},
    "Solidity": {"label": "CryptoZombies interactive course", "url": "https://cryptozombies.io/"},
    "Blockchain": {"label": "ethereum.org developer docs", "url": "https://ethereum.org/en/developers/docs/"},
    "Flutter": {"label": "Flutter's official codelabs", "url": "https://docs.flutter.dev/codelabs"},
    "Android": {"label": "Android developer fundamentals", "url": "https://developer.android.com/courses"},
    "iOS": {"label": "Apple's Swift tutorials", "url": "https://developer.apple.com/tutorials/swiftui"},
    "Cybersecurity": {"label": "TryHackMe beginner path", "url": "https://tryhackme.com/"},
    "IoT": {"label": "Arduino's official guide", "url": "https://docs.arduino.cc/learn/"},
    "UI/UX": {"label": "Google's UX design basics", "url": "https://www.coursera.org/professional-certificates/google-ux-design"},
    "AI": {"label": "Google's AI essentials", "url": "https://www.coursera.org/learn/ai-essentials-google"},
    "Data Science": {"label": "Kaggle Learn", "url": "https://www.kaggle.com/learn"},
}


def _fallback_resource(skill: str) -> dict[str, str]:
    return {"label": f"Search: learn {skill}", "url": f"https://www.google.com/search?q=learn+{quote(skill)}"}


@dataclass
class SkillGap:
    skill: str
    events_seen: int
    would_unlock: int
    avg_gain: float
    sample_titles: list[str] = field(default_factory=list)
    resource_label: str = ""
    resource_url: str = ""


def _shadow_profile(profile: Profile, extra_skill: str) -> SimpleNamespace:
    """A duck-typed stand-in with one skill added, so scoring never touches
    the real ORM row — no risk of a stray commit persisting a fake skill."""
    return SimpleNamespace(
        skills=[*(profile.skills or []), extra_skill],
        interests=profile.interests or [],
        prefer_mode=profile.prefer_mode,
        india_only=profile.india_only,
        min_prize_inr=profile.min_prize_inr,
        free_only=profile.free_only,
        team_size=profile.team_size,
    )


def analyse(db: Session, profile: Profile) -> dict:
    today = date.today()
    rows = db.scalars(select(Hackathon).where(Hackathon.status == "open")).all()
    events = [row for row, _mirrors in collapse(rows)][:MAX_EVENTS_SCANNED]

    my_skills = {canonical_skill(s) for s in (profile.skills or []) if s}

    baseline: list[tuple[Hackathon, dict]] = []
    candidate_counts: dict[str, int] = {}
    candidate_events: dict[str, list[Hackathon]] = {}

    # Only genuine technologies are learnable "skills". canonical_skill()
    # falls back to title-casing anything unrecognised, which would turn
    # theme tags like "Social Good" or "Beginner Friendly" into fake
    # skill suggestions — so candidates are filtered to TECH_TAGS' own
    # vocabulary rather than trusting the fallback.
    known_skills = {label.lower() for label in TECH_TAGS}

    for event in events:
        result = match_score(event, profile, today=today)
        baseline.append((event, result))
        for tag in event.tags or []:
            key = canonical_skill(tag)
            if key and key.lower() in known_skills and key not in my_skills:
                candidate_counts[key] = candidate_counts.get(key, 0) + 1
                candidate_events.setdefault(key, []).append(event)

    total_open = len(events)
    currently_good = sum(1 for _, r in baseline if r["level"] in GOOD_THRESHOLD_LEVELS)

    top_candidates = sorted(candidate_counts.items(), key=lambda kv: -kv[1])[
        :MAX_CANDIDATES_EVALUATED
    ]

    results: list[SkillGap] = []
    for skill, freq in top_candidates:
        shadow = _shadow_profile(profile, skill)
        related = candidate_events[skill]

        deltas: list[int] = []
        unlocks = 0
        for event in related:
            before = match_score(event, profile, today=today)
            after = match_score(event, shadow, today=today)
            deltas.append(after["score"] - before["score"])
            if before["level"] not in GOOD_THRESHOLD_LEVELS and after["level"] in GOOD_THRESHOLD_LEVELS:
                unlocks += 1

        resource = LEARNING_RESOURCES.get(skill, _fallback_resource(skill))
        results.append(
            SkillGap(
                skill=skill,
                events_seen=freq,
                would_unlock=unlocks,
                avg_gain=round(sum(deltas) / len(deltas), 1) if deltas else 0.0,
                sample_titles=[e.title for e in related[:3]],
                resource_label=resource["label"],
                resource_url=resource["url"],
            )
        )

    # Skills that unlock the most events win; ties broken by average gain,
    # so a skill that helps a lot on fewer events still surfaces.
    results.sort(key=lambda r: (-r.would_unlock, -r.avg_gain))

    return {
        "total_open": total_open,
        "currently_good": currently_good,
        "skills": results[:TOP_RESULTS],
    }
