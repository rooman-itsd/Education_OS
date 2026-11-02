"""HTTP surface of skill-progress, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/skill-progress. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ServiceError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["skill-progress"])

LIMIT_50 = Query(50, ge=1, le=200)
LIMIT_100 = Query(100, ge=1, le=500)
OFFSET = Query(0, ge=0)
LEARNER = Path(pattern=s.UUID_PATTERN)


def _id():
    """An optional UUID query parameter (a fresh Query each time: FastAPI binds one to one parameter)."""
    return Query(None, pattern=s.UUID_PATTERN)


def _run(fn, *args):
    try:
        return fn(*args)
    except ServiceError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- frameworks


@router.get("/frameworks")
def list_frameworks(
    status: s.FrameworkStatus | None = None,
    limit: int = LIMIT_50,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.FRAMEWORK_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_frameworks(db, status, limit, offset)


@router.post("/frameworks", status_code=201)
def create_framework(
    body: s.FrameworkIn, a: Actor = Depends(require(svc.FRAMEWORK_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_framework, db, a, s.dump(body))


@router.get("/frameworks/{framework_id}")
def get_framework(framework_id: str, _: Actor = Depends(require(svc.FRAMEWORK_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_framework, db, framework_id)


@router.patch("/frameworks/{framework_id}")
def update_framework(
    framework_id: str,
    body: s.FrameworkPatch,
    a: Actor = Depends(require(svc.FRAMEWORK_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_framework, db, a, framework_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- skills


@router.get("/skills")
def list_skills(
    framework_id: str | None = _id(),
    category: str | None = None,
    parent_skill_id: str | None = _id(),
    limit: int = LIMIT_100,
    offset: int = OFFSET,
    _: Actor = Depends(require(svc.FRAMEWORK_READ)),
    db: Session = Depends(get_db),
):
    filters = {"framework_id": framework_id, "category": category, "parent_skill_id": parent_skill_id}
    return svc.list_skills(db, filters, limit, offset)


@router.post("/skills", status_code=201)
def create_skill(body: s.SkillIn, a: Actor = Depends(require(svc.FRAMEWORK_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_skill, db, a, s.dump(body))


@router.get("/skills/{skill_id}")
def get_skill(skill_id: str, _: Actor = Depends(require(svc.FRAMEWORK_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_skill, db, skill_id)


@router.patch("/skills/{skill_id}")
def update_skill(
    skill_id: str, body: s.SkillPatch, a: Actor = Depends(require(svc.FRAMEWORK_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.update_skill, db, a, skill_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- rubrics


@router.get("/rubrics")
def list_rubrics(
    skill_id: str | None = _id(),
    framework_id: str | None = _id(),
    _: Actor = Depends(require(svc.FRAMEWORK_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_rubrics(db, skill_id, framework_id)


@router.post("/rubrics", status_code=201)
def create_rubric(body: s.RubricIn, a: Actor = Depends(require(svc.FRAMEWORK_WRITE)), db: Session = Depends(get_db)):
    return _run(svc.create_rubric, db, a, s.dump(body))


@router.get("/rubrics/{rubric_id}")
def get_rubric(rubric_id: str, _: Actor = Depends(require(svc.FRAMEWORK_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_rubric, db, rubric_id)


# ---------------------------------------------------------------- assessments


@router.get("/assessments")
def list_assessments(
    learner_id: str | None = _id(),
    evaluator_id: str | None = _id(),
    skill_id: str | None = _id(),
    from_date: date | None = None,
    to_date: date | None = None,
    limit: int = LIMIT_50,
    offset: int = OFFSET,
    a: Actor = Depends(require(svc.ASSESSMENT_READ)),
    db: Session = Depends(get_db),
):
    if from_date and to_date and from_date > to_date:
        raise HTTPException(400, {"code": "invalid_period", "message": "from_date must not be after to_date"})
    filters = {
        "learner_id": learner_id,
        "evaluator_id": evaluator_id,
        "skill_id": skill_id,
        "from_date": from_date,
        "to_date": to_date,
    }
    return svc.list_assessments(db, a, filters, limit, offset)


@router.post("/assessments", status_code=201)
def record_assessment(
    body: s.AssessmentIn, a: Actor = Depends(require(svc.ASSESSMENT_RECORD)), db: Session = Depends(get_db)
):
    return _run(svc.record_assessment, db, a, s.dump(body))


@router.get("/assessments/{assessment_id}")
def get_assessment(assessment_id: str, a: Actor = Depends(require(svc.ASSESSMENT_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_assessment, db, a, assessment_id)


@router.post("/assessments/{assessment_id}/verify")
def verify_assessment(
    assessment_id: str, a: Actor = Depends(require(svc.ASSESSMENT_APPROVE)), db: Session = Depends(get_db)
):
    return _run(svc.verify_assessment, db, a, assessment_id)


@router.post("/assessments/{assessment_id}/void")
def void_assessment(
    assessment_id: str, a: Actor = Depends(require(svc.ASSESSMENT_DELETE)), db: Session = Depends(get_db)
):
    return _run(svc.void_assessment, db, a, assessment_id)


# ---------------------------------------------------------------- learners


@router.get("/learners/{learner_id}/progress")
def get_learner_progress(
    learner_id: str = LEARNER,
    framework_id: str | None = _id(),
    a: Actor = Depends(require(svc.PROGRESS_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.learner_progress, db, a, learner_id, framework_id)


@router.get("/learners/{learner_id}/timeline")
def get_learner_timeline(
    learner_id: str = LEARNER,
    skill_id: str | None = _id(),
    limit: int = LIMIT_100,
    a: Actor = Depends(require(svc.PROGRESS_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.learner_timeline, db, a, learner_id, skill_id, limit)
