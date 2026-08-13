"""Work out what a form field is asking for, and answer it from the profile.

Every hackathon platform words its questions differently — "Institution",
"College/University", "Where do you study?" all want the same fact. This
module maps arbitrary field labels onto profile attributes and reports how
confident it is.

Matching is rule-based so it works with no API key and no network. When
ANTHROPIC_API_KEY is set, `llm_resolve` handles the labels the rules could
not place, which in practice is the unusual phrasings and the open-ended
essay questions.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field as dc_field

# --------------------------------------------------------------------------
# What each profile attribute answers to.
#
# `terms` are matched against the normalised label. `strong` phrases score
# higher because they are unambiguous; a bare "name" is not.
# --------------------------------------------------------------------------

FIELD_VOCAB: dict[str, dict] = {
    "full_name": {
        "strong": ["full name", "your name", "candidate name", "participant name",
                   "student name", "applicant name", "first and last name"],
        "terms": ["name"],
        "avoid": ["team", "college", "university", "project", "user", "institution",
                  "father", "mother", "guardian", "event", "company"],
    },
    "email": {
        "strong": ["email address", "e-mail", "email id", "mail id", "contact email"],
        "terms": ["email", "mail"],
        "avoid": ["team", "mentor", "alternate", "parent"],
    },
    "phone": {
        "strong": ["phone number", "mobile number", "contact number", "whatsapp number"],
        "terms": ["phone", "mobile", "contact no", "whatsapp"],
        "avoid": ["parent", "guardian", "emergency", "alternate"],
    },
    "college": {
        "strong": ["college name", "university name", "institution", "institute name",
                   "school name", "organisation name", "organization name",
                   "where do you study", "your college", "college/university"],
        "terms": ["college", "university", "institute", "campus", "school"],
        "avoid": ["email", "id", "city", "code"],
    },
    "degree": {
        "strong": ["educational qualification", "current academic program", "degree",
                   "course", "programme", "program of study", "qualification"],
        "terms": ["degree", "course", "qualification", "program", "programme"],
        "avoid": ["branch", "specialisation", "specialization", "stream"],
    },
    "branch": {
        "strong": ["branch", "specialisation", "specialization", "stream",
                   "department", "major", "field of study"],
        "terms": ["branch", "stream", "department", "major", "discipline"],
        "avoid": [],
    },
    "year_of_study": {
        "strong": ["year of study", "current year", "academic year", "which year",
                   "study year", "year of college"],
        "terms": ["year of study", "current year", "semester"],
        "avoid": ["graduation", "passing", "birth", "founded"],
    },
    "graduation_year": {
        "strong": ["graduation year", "year of graduation", "passing year",
                   "year of passing", "expected graduation"],
        "terms": ["graduation", "passing out", "batch"],
        "avoid": [],
    },
    "registration_number": {
        "strong": ["registration number", "roll number", "enrollment number",
                   "student id", "university roll", "reg no", "usn", "srn"],
        "terms": ["registration", "roll", "enrolment", "enrollment", "student id",
                  "reg no", "usn", "srn"],
        "avoid": ["team"],
    },
    "city": {
        "strong": ["city", "your location", "current city", "town"],
        "terms": ["city", "location", "place"],
        "avoid": ["college", "institute", "event", "venue"],
    },
    "github_url": {
        "strong": ["github profile", "github link", "github url", "github"],
        "terms": ["github", "git hub"],
        "avoid": ["repository of the project", "project repo"],
    },
    "linkedin_url": {
        "strong": ["linkedin profile", "linkedin link", "linkedin url", "linkedin"],
        "terms": ["linkedin", "linked in"],
        "avoid": [],
    },
    "portfolio_url": {
        "strong": ["portfolio", "personal website", "website link", "portfolio url"],
        "terms": ["portfolio", "website", "personal site", "blog"],
        "avoid": ["college website", "company"],
    },
    "resume_url": {
        "strong": ["resume", "cv link", "resume link", "curriculum vitae"],
        "terms": ["resume", "cv"],
        "avoid": [],
    },
    "skills": {
        "strong": ["technical skills", "your skills", "skills", "technologies you know",
                   "tech stack", "programming languages"],
        "terms": ["skill", "technolog", "tech stack", "languages", "expertise"],
        "avoid": ["soft skill"],
    },
    "team_name": {
        "strong": ["team name", "name of your team", "squad name"],
        "terms": ["team name"],
        "avoid": [],
    },
    "bio": {
        "strong": ["about yourself", "tell us about you", "short bio", "introduce yourself",
                   "about you", "profile summary"],
        "terms": ["about your", "bio", "introduce"],
        "avoid": ["project", "team"],
    },
    "experience": {
        "strong": ["prior experience", "relevant experience", "work experience",
                   "past projects", "previous hackathons", "your experience"],
        "terms": ["experience", "past project", "previously"],
        "avoid": [],
    },
    "achievements": {
        "strong": ["achievements", "accomplishments", "awards", "recognitions"],
        "terms": ["achievement", "award", "accomplish"],
        "avoid": [],
    },
}

# Open-ended questions: no stored fact answers them, so they are written.
GENERATIVE_PATTERNS: list[tuple[str, str]] = [
    (r"why (do|would) you (want to )?(participate|join|apply|attend)", "motivation"),
    (r"why should we (select|choose|pick) you", "pitch"),
    (r"what (do you )?(hope|expect) to (learn|gain|achieve)", "goals"),
    (r"(project|solution) (idea|description|abstract|summary|proposal)", "project"),
    (r"describe your (idea|project|solution|approach)", "project"),
    (r"problem (statement|you want to solve)", "project"),
    (r"how will you (use|apply|contribute)", "motivation"),
    (r"tell us (about|why)", "motivation"),
    (r"what makes you", "pitch"),
    (r"your (motivation|interest) ", "motivation"),
]

# Fields nothing should ever be typed into automatically.
SENSITIVE_PATTERNS = [
    r"password", r"\botp\b", r"\bcvv\b", r"card number", r"\bupi\b",
    r"aadha?ar", r"\bpan\b", r"passport", r"account number", r"ifsc",
    r"\bsignature\b", r"declaration", r"\bi agree\b", r"terms and conditions",
    r"\bconsent\b", r"date of birth", r"\bdob\b",
]

_WS = re.compile(r"\s+")
_PUNCT = re.compile(r"[^a-z0-9 /]+")


def normalise(label: str) -> str:
    text = (label or "").lower().replace("*", " ").replace("_", " ")
    text = _PUNCT.sub(" ", text)
    return _WS.sub(" ", text).strip()


@dataclass
class FieldMatch:
    label: str
    profile_field: str | None = None
    value: str = ""
    confidence: float = 0.0
    action: str = "skip"           # fill | generate | skip | sensitive
    reason: str = ""
    options: list[str] = dc_field(default_factory=list)


def is_sensitive(label: str) -> bool:
    text = normalise(label)
    return any(re.search(p, text) for p in SENSITIVE_PATTERNS)


def generative_kind(label: str) -> str | None:
    text = normalise(label)
    for pattern, kind in GENERATIVE_PATTERNS:
        if re.search(pattern, text):
            return kind
    # A long question with a textarea is usually an essay prompt.
    if text.endswith("?") and len(text.split()) >= 5:
        return "motivation"
    return None


def score_field(label: str, key: str, spec: dict) -> float:
    """0–1 confidence that `label` is asking for profile attribute `key`."""
    text = normalise(label)
    if not text:
        return 0.0

    if any(bad in text for bad in spec.get("avoid", [])):
        return 0.0

    for phrase in spec.get("strong", []):
        if phrase in text:
            # An exact label is near-certain; a phrase inside a longer
            # question slightly less so.
            return 1.0 if text == phrase else 0.92

    for term in spec.get("terms", []):
        if re.search(rf"\b{re.escape(term)}", text):
            # Short labels are more likely to be exactly this field.
            return 0.78 if len(text.split()) <= 4 else 0.62

    return 0.0


def match_label(label: str) -> tuple[str | None, float]:
    """Best profile attribute for a label, with confidence."""
    best_key, best_score = None, 0.0
    for key, spec in FIELD_VOCAB.items():
        score = score_field(label, key, spec)
        if score > best_score:
            best_key, best_score = key, score
    return best_key, best_score


def profile_values(profile, user=None) -> dict[str, str]:
    """Flatten a profile into the values a form might ask for."""
    skills = ", ".join(profile.skills or [])
    return {
        "full_name": profile.name or (user.name if user else ""),
        "email": profile.email or "",
        "phone": profile.phone or (user.phone if user else ""),
        "college": profile.college or "",
        "degree": profile.degree or "",
        "branch": profile.branch or "",
        "year_of_study": profile.year_of_study or "",
        "graduation_year": profile.graduation_year or "",
        "registration_number": profile.registration_number or "",
        "city": profile.city or "",
        "github_url": profile.github_url or "",
        "linkedin_url": profile.linkedin_url or "",
        "portfolio_url": profile.portfolio_url or "",
        "resume_url": profile.resume_url or "",
        "skills": skills,
        "team_name": profile.team_name or "",
        "bio": profile.bio or "",
        "experience": profile.experience or "",
        "achievements": profile.achievements or "",
    }


def completeness(values: dict[str, str]) -> dict:
    """How much of the profile is usable, and what is missing."""
    # Weighted: a form is far more likely to ask for a college than a resume.
    weights = {
        "full_name": 3, "email": 3, "phone": 3, "college": 3, "degree": 2,
        "branch": 2, "year_of_study": 2, "registration_number": 2, "skills": 3,
        "github_url": 2, "linkedin_url": 1, "portfolio_url": 1, "city": 1,
        "graduation_year": 1, "bio": 2, "experience": 1, "achievements": 1,
    }
    total = sum(weights.values())
    have = sum(w for k, w in weights.items() if (values.get(k) or "").strip())
    missing = [k for k in weights if not (values.get(k) or "").strip()]
    return {
        "percent": round(100 * have / total),
        "missing": missing,
    }


def analyse(fields: list[dict], profile, user=None) -> list[FieldMatch]:
    """Classify each detected form field and attach a value where possible.

    `fields` are dicts as sent by the extension: {label, name, type, options}.
    """
    values = profile_values(profile, user)
    results: list[FieldMatch] = []

    for raw in fields:
        label = (raw.get("label") or raw.get("name") or "").strip()
        input_type = (raw.get("type") or "text").lower()
        options = raw.get("options") or []

        if not label:
            results.append(FieldMatch(label="", action="skip", reason="no label found"))
            continue

        if is_sensitive(label) or input_type in {"password", "file"}:
            results.append(FieldMatch(
                label=label, action="sensitive",
                reason="Left for you — credentials, identity documents, consent "
                       "and uploads are never filled automatically.",
            ))
            continue

        key, score = match_label(label)
        value = values.get(key, "") if key else ""

        if key and value and score >= 0.6:
            # For a dropdown, only offer a value the control actually has.
            if options:
                picked = _best_option(value, options)
                if picked is None:
                    results.append(FieldMatch(
                        label=label, profile_field=key, confidence=round(score, 2),
                        action="skip", options=options,
                        reason=f"No option matches your {key.replace('_', ' ')}.",
                    ))
                    continue
                value = picked
            results.append(FieldMatch(
                label=label, profile_field=key, value=value,
                confidence=round(score, 2), action="fill",
                reason=f"from your {key.replace('_', ' ')}",
            ))
            continue

        kind = generative_kind(label)
        if kind:
            results.append(FieldMatch(
                label=label, action="generate", confidence=0.0,
                reason=kind, profile_field=None,
            ))
            continue

        if key and not value:
            results.append(FieldMatch(
                label=label, profile_field=key, confidence=round(score, 2),
                action="skip",
                reason=f"Your profile has no {key.replace('_', ' ')} yet.",
            ))
            continue

        results.append(FieldMatch(
            label=label, action="skip", reason="Could not tell what this field wants."
        ))

    return results


def _best_option(value: str, options: list[str]) -> str | None:
    """Pick the dropdown option closest to a profile value."""
    v = normalise(value)
    if not v:
        return None
    norm = [(o, normalise(o)) for o in options]

    for original, cleaned in norm:
        if cleaned == v:
            return original
    for original, cleaned in norm:
        if v in cleaned or cleaned in v:
            return original
    # Token overlap, for "B.Tech" against "Bachelor of Technology (B.Tech)".
    v_tokens = set(v.split())
    best, best_overlap = None, 0
    for original, cleaned in norm:
        overlap = len(v_tokens & set(cleaned.split()))
        if overlap > best_overlap:
            best, best_overlap = original, overlap
    return best if best_overlap else None


# --------------------------------------------------------------------------
# Optional LLM pass for labels the rules could not place
# --------------------------------------------------------------------------

_RESOLVE_PROMPT = """You map form field labels onto a user profile. Return ONLY JSON.

Profile attributes available:
{keys}

For each label, decide which attribute it asks for, or "generate" if it is an
open-ended question needing a written answer, or "skip" if neither fits.

Return: {{"results": [{{"label": "...", "profile_field": "<attribute|generate|skip>", "confidence": 0.0-1.0}}]}}

Labels:
{labels}"""


def llm_resolve(labels: list[str]) -> dict[str, tuple[str, float]]:
    """Ask Claude about labels the rules could not place. {} if unavailable."""
    from ..config import settings

    if not settings.ANTHROPIC_API_KEY or not labels:
        return {}
    try:
        import anthropic
    except ImportError:
        return {}

    try:
        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        resp = client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=900,
            messages=[{
                "role": "user",
                "content": _RESOLVE_PROMPT.format(
                    keys=", ".join(FIELD_VOCAB),
                    labels="\n".join(f"- {label}" for label in labels[:40]),
                ),
            }],
        )
        text = "".join(b.text for b in resp.content if b.type == "text")
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            return {}
        data = json.loads(match.group(0))
        return {
            item["label"]: (item.get("profile_field", "skip"), float(item.get("confidence", 0)))
            for item in data.get("results", [])
            if item.get("label")
        }
    except Exception:
        # Enrichment is optional; the rule-based result already stands.
        return {}
