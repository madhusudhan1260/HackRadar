"""Skill Builder: what to learn next, ranked by measured impact."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..deps import get_current_profile
from ..models import Profile
from ..schemas import SkillGapsOut
from ..services import skill_gaps

router = APIRouter(prefix="/api/skills", tags=["skills"])


@router.get("/gaps", response_model=SkillGapsOut)
def gaps(db: Session = Depends(get_db), profile: Profile = Depends(get_current_profile)):
    return skill_gaps.analyse(db, profile)
