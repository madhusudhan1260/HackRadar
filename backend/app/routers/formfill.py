"""Form-filling API used by the browser extension.

The extension reads the fields off whatever application page the user is
on and posts the labels here. Nothing about the page is stored: labels go
in, values come back, and the extension does the filling locally.

Deliberately never submits anything. The response is a proposal the user
reviews in the page before pressing the site's own submit button.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_profile, get_current_user
from ..models import Hackathon, Profile, User
from ..schemas import (
    FormAnalyseIn,
    FormAnalyseOut,
    FormFieldOut,
    GenerateAnswerIn,
    GenerateAnswerOut,
    ProfileReadinessOut,
)
from ..services import answer_writer, field_matcher

router = APIRouter(prefix="/api/form", tags=["form-filler"])


def _hackathon_context(db: Session, hackathon_id: int | None, page_title: str) -> dict | None:
    """What the answer writer knows about the event being applied to."""
    row = db.get(Hackathon, hackathon_id) if hackathon_id else None
    if row is None and page_title:
        # Fall back to a loose title match, so the extension still gets
        # context when it only knows the page heading.
        needle = page_title.strip().lower()[:60]
        if needle:
            row = (
                db.query(Hackathon)
                .filter(Hackathon.title.ilike(f"%{needle}%"))
                .first()
            )
    if row is None:
        return {"title": page_title} if page_title else None
    return {
        "id": row.id,
        "title": row.title,
        "tags": row.tags or [],
        "categories": row.categories or [],
        "description": row.description,
    }


@router.get("/readiness", response_model=ProfileReadinessOut)
def readiness(
    profile: Profile = Depends(get_current_profile),
    user: User = Depends(get_current_user),
):
    """How much of the profile is filled in — shown before analysing a page."""
    values = field_matcher.profile_values(profile, user)
    stats = field_matcher.completeness(values)
    return ProfileReadinessOut(
        percent=stats["percent"],
        missing=stats["missing"],
        available=[k for k, v in values.items() if (v or "").strip()],
    )


@router.post("/analyse", response_model=FormAnalyseOut)
def analyse(
    payload: FormAnalyseIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
    user: User = Depends(get_current_user),
):
    """Map detected form fields onto the profile and propose values."""
    matches = field_matcher.analyse(
        [f.model_dump() for f in payload.fields], profile, user
    )

    # Hand anything the rules could not place to the LLM, when configured.
    unresolved = [m.label for m in matches if m.action == "skip" and m.label]
    if unresolved:
        resolved = field_matcher.llm_resolve(unresolved)
        if resolved:
            values = field_matcher.profile_values(profile, user)
            for match in matches:
                guess = resolved.get(match.label)
                if not guess or match.action != "skip":
                    continue
                key, confidence = guess
                if key == "generate":
                    match.action, match.reason = "generate", "motivation"
                elif key in values and values[key].strip() and confidence >= 0.6:
                    match.action = "fill"
                    match.profile_field = key
                    match.value = values[key]
                    match.confidence = round(confidence, 2)
                    match.reason = f"from your {key.replace('_', ' ')} (AI matched)"

    context = _hackathon_context(db, payload.hackathon_id, payload.page_title)

    # Draft the open questions in the same round trip.
    if payload.write_answers:
        for match in matches:
            if match.action == "generate":
                written = answer_writer.draft(match.reason or "motivation", profile, context)
                match.value = written["text"]
                match.confidence = 0.9 if written["source"] == "claude" else 0.75
                match.reason = (
                    "written by Claude — review before submitting"
                    if written["source"] == "claude"
                    else "drafted from your profile — edit before submitting"
                )

    stats = field_matcher.completeness(field_matcher.profile_values(profile, user))
    filled = [m for m in matches if m.action in {"fill", "generate"} and m.value]

    return FormAnalyseOut(
        hackathon=(context or {}).get("title", ""),
        profile_complete=stats["percent"],
        total_fields=len(matches),
        will_fill=len(filled),
        needs_review=sum(1 for m in matches if m.action == "generate"),
        left_alone=sum(1 for m in matches if m.action in {"skip", "sensitive"}),
        fields=[
            FormFieldOut(
                label=m.label,
                profile_field=m.profile_field,
                value=m.value,
                confidence=m.confidence,
                action=m.action,
                reason=m.reason,
            )
            for m in matches
        ],
    )


@router.post("/generate", response_model=GenerateAnswerOut)
def generate(
    payload: GenerateAnswerIn,
    db: Session = Depends(get_db),
    profile: Profile = Depends(get_current_profile),
):
    """Rewrite a single open-ended answer, for the 'regenerate' button."""
    context = _hackathon_context(db, payload.hackathon_id, payload.page_title)
    kind = payload.kind or field_matcher.generative_kind(payload.question) or "motivation"
    written = answer_writer.draft(kind, profile, context)
    return GenerateAnswerOut(
        question=payload.question,
        answer=written["text"],
        source=written["source"],
        kind=kind,
    )
