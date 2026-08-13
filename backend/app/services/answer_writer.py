"""Draft answers to the open-ended questions on an application.

"Why do you want to participate?" has no stored answer, so it has to be
written from what we know: the user's skills and interests, and the
hackathon's theme.

Templates produce a usable draft with no API key. With ANTHROPIC_API_KEY
set the same inputs go to Claude, which reads better. Either way the text
is a draft the user is expected to edit — it is never submitted for them.
"""
from __future__ import annotations

import re

from ..config import settings

# --------------------------------------------------------------------------
# Templates
# --------------------------------------------------------------------------

_MOTIVATION = (
    "I want to take part in {event} because it lines up closely with what I "
    "actually work on. I build with {skills}, and {theme_clause} I am looking "
    "for a chance to apply that to a real problem under time pressure, learn "
    "from people solving it differently, and come away with something I have "
    "shipped rather than only studied."
)

_PITCH = (
    "I bring hands-on experience with {skills}, and I am comfortable owning a "
    "feature end to end rather than waiting to be handed one. {theme_sentence}"
    "I work well in a small team, I would rather ship something rough and "
    "improve it than plan indefinitely, and I take feedback without ego."
)

_GOALS = (
    "I want to come out of {event} having built something that works, not just "
    "a prototype that demos well. Concretely: deepen my {skills_short}, learn "
    "where my current approach breaks under real constraints, and get feedback "
    "from people further along than me."
)

_PROJECT = (
    "I plan to build a solution around {theme_short}, using {skills_short}. The "
    "aim is a working prototype that solves one specific problem properly "
    "rather than several partially. I will start from the smallest version that "
    "delivers real value, get it running end to end, and improve it with the "
    "time left.\n\n[Replace this with your actual idea before submitting.]"
)

_TEMPLATES = {
    "motivation": _MOTIVATION,
    "pitch": _PITCH,
    "goals": _GOALS,
    "project": _PROJECT,
}


def _skills_phrase(skills: list[str], limit: int = 4) -> str:
    picked = [s for s in (skills or []) if s][:limit]
    if not picked:
        return "software"
    if len(picked) == 1:
        return picked[0]
    return ", ".join(picked[:-1]) + " and " + picked[-1]


def _theme(hackathon: dict | None) -> tuple[str, str, str]:
    """(clause, sentence, short) describing the event's subject."""
    if not hackathon:
        return ("", "", "this problem space")
    tags = [t for t in (hackathon.get("tags") or []) if t][:3]
    cats = [c for c in (hackathon.get("categories") or []) if c and c != "general"][:2]
    subject = ", ".join(tags) or ", ".join(c.replace("-", "/") for c in cats)
    if not subject:
        return ("", "", "this problem space")
    return (
        f"this event's focus on {subject} is squarely in that area, so ",
        f"The focus on {subject} is where I already spend my time. ",
        subject,
    )


def draft(kind: str, profile, hackathon: dict | None = None) -> dict:
    """Return {text, source} for an open-ended question."""
    event = (hackathon or {}).get("title") or "this hackathon"
    skills = profile.skills or []
    clause, sentence, short = _theme(hackathon)

    llm = _llm_draft(kind, profile, hackathon)
    if llm:
        return {"text": llm, "source": "claude"}

    template = _TEMPLATES.get(kind, _MOTIVATION)
    text = template.format(
        event=event,
        skills=_skills_phrase(skills),
        skills_short=_skills_phrase(skills, 2),
        theme_clause=clause,
        theme_sentence=sentence,
        theme_short=short,
    )
    return {"text": re.sub(r"\s+", " ", text).strip(), "source": "template"}


_PROMPT = """Write a short answer to a hackathon application question, in the
first person, as this applicant. 60-90 words. Plain, direct, specific. No
buzzwords, no "passionate", no "leverage", no exclamation marks. Do not invent
achievements, projects or experience that are not listed below.

Question: {question}

Applicant skills: {skills}
Applicant interests: {interests}
{extra}
Hackathon: {event}
Hackathon focus: {focus}

Return only the answer text."""

_QUESTIONS = {
    "motivation": "Why do you want to participate in this hackathon?",
    "pitch": "Why should we select you?",
    "goals": "What do you hope to learn or achieve?",
    "project": "Describe the project or solution you plan to build.",
}


def _llm_draft(kind: str, profile, hackathon: dict | None) -> str | None:
    if not settings.ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
    except ImportError:
        return None

    extra = ""
    if (profile.experience or "").strip():
        extra = f"Applicant experience: {profile.experience.strip()[:400]}\n"

    focus = ", ".join((hackathon or {}).get("tags") or []) or ", ".join(
        (hackathon or {}).get("categories") or []
    ) or "general"

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=320,
            messages=[{
                "role": "user",
                "content": _PROMPT.format(
                    question=_QUESTIONS.get(kind, _QUESTIONS["motivation"]),
                    skills=", ".join(profile.skills or []) or "not listed",
                    interests=", ".join(profile.interests or []) or "not listed",
                    extra=extra,
                    event=(hackathon or {}).get("title") or "a hackathon",
                    focus=focus,
                ),
            }],
        )
        text = "".join(b.text for b in resp.content if b.type == "text").strip()
        return text or None
    except Exception:
        return None
