"""HTTP surface of projects, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/projects. Handlers only map HTTP to the use cases in application/service.py; each declares the
permission the contract names for it. Which project the caller may touch (a guide's own, a member's own, the lead's
proposal) is checked in the use case."""

from __future__ import annotations

from typing import Annotated, Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, ProjectsError
from . import schemas as s
from .deps import no_nul, require

# Every request is checked for NUL characters in its path and query first (deps.no_nul).
router = APIRouter(tags=["projects"], dependencies=[Depends(no_nul)])

PathId = Annotated[str, Path(pattern=s.UUID_PATTERN)]
LIMIT = Query(20, ge=1, le=100)
QueryId = Annotated[str | None, Query(pattern=s.UUID_PATTERN)]
Status = Literal["proposed", "active", "submitted", "completed", "rejected", "cancelled"]

# Who may see a project: every project, the projects the caller guides, or the caller's own.
SEE_PROJECT = (svc.PROJECT_READ, svc.GUIDANCE_READ, svc.SELF_READ)


def _run(fn, *args):
    try:
        return fn(*args)
    except ProjectsError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- projects


@router.get("/projects")
def list_projects(
    status: Status | None = None,
    kind: str | None = Query(default=None, max_length=100),
    academic_year: str | None = Query(default=None, max_length=20),
    guide_id: QueryId = None,
    member_id: QueryId = None,
    q: str | None = Query(default=None, max_length=200),
    cursor: str | None = Query(default=None, max_length=64),
    limit: int = LIMIT,
    a: Actor = Depends(require(svc.PROJECT_READ, svc.GUIDANCE_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "status": status,
        "kind": kind,
        "academic_year": academic_year,
        "guide_id": guide_id,
        "member_id": member_id,
        "q": q,
    }
    return svc.list_projects(db, a, filters, cursor, limit)


@router.post("/projects", status_code=201)
def create_project(
    body: s.ProjectCreateIn,
    a: Actor = Depends(require(svc.PROJECT_MANAGE, svc.SELF_PROPOSE)),
    db: Session = Depends(get_db),
):
    return _run(svc.create_project, db, a, body.model_dump())


@router.get("/projects/{project_id}")
def get_project(project_id: PathId, a: Actor = Depends(require(*SEE_PROJECT)), db: Session = Depends(get_db)):
    return _run(svc.get_project, db, a, project_id)


@router.patch("/projects/{project_id}")
def update_project(
    body: s.ProjectFieldsIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.PROJECT_MANAGE, svc.SELF_PROPOSE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_project, db, a, project_id, s.dump(body))


@router.post("/projects/{project_id}/decision")
def decide_project(
    body: s.DecisionIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.decide_project, db, a, project_id, body.model_dump())


@router.post("/projects/{project_id}/members", status_code=201)
def add_member(
    body: s.MemberIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.PROJECT_MANAGE, svc.SELF_PROPOSE)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_member, db, a, project_id, body.person_id, body.role)


@router.delete("/projects/{project_id}/members/{person_id}", status_code=204)
def remove_member(
    project_id: PathId,
    person_id: PathId,
    a: Actor = Depends(require(svc.PROJECT_MANAGE, svc.SELF_PROPOSE)),
    db: Session = Depends(get_db),
):
    _run(svc.remove_member, db, a, project_id, person_id)
    return Response(status_code=204)


@router.put("/projects/{project_id}/guides")
def set_guides(
    body: s.GuidesIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.set_guides, db, a, project_id, body.guide_ids)


@router.post("/projects/{project_id}/cancel")
def cancel_project(
    body: s.ReasonIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_project, db, a, project_id, body.reason)


# ---------------------------------------------------------------- milestones


@router.get("/projects/{project_id}/milestones")
def list_milestones(project_id: PathId, a: Actor = Depends(require(*SEE_PROJECT)), db: Session = Depends(get_db)):
    return _run(svc.list_milestones, db, a, project_id)


@router.post("/projects/{project_id}/milestones", status_code=201)
def create_milestone(
    body: s.MilestoneIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.MILESTONE_MANAGE, svc.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.create_milestone, db, a, project_id, s.dump(body))


@router.patch("/milestones/{milestone_id}")
def update_milestone(
    body: s.MilestoneUpdateIn,
    milestone_id: PathId,
    a: Actor = Depends(require(svc.MILESTONE_MANAGE, svc.PROJECT_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_milestone, db, a, milestone_id, s.dump(body))


# ---------------------------------------------------------------- submissions, reviews and evaluation


@router.get("/milestones/{milestone_id}/submissions")
def list_submissions(milestone_id: PathId, a: Actor = Depends(require(*SEE_PROJECT)), db: Session = Depends(get_db)):
    return _run(svc.list_submissions, db, a, milestone_id)


@router.post("/milestones/{milestone_id}/submissions", status_code=201)
def submit_milestone(
    body: s.SubmissionIn,
    milestone_id: PathId,
    a: Actor = Depends(require(svc.SELF_SUBMIT)),
    db: Session = Depends(get_db),
):
    return _run(svc.submit_milestone, db, a, milestone_id, body.model_dump())


@router.post("/milestones/{milestone_id}/review")
def review_milestone(
    body: s.ReviewIn,
    milestone_id: PathId,
    a: Actor = Depends(require(svc.REVIEW_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(svc.review_milestone, db, a, milestone_id, body.model_dump())


@router.post("/projects/{project_id}/submit", status_code=201)
def submit_project(
    body: s.SubmissionIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.SELF_SUBMIT)),
    db: Session = Depends(get_db),
):
    return _run(svc.submit_project, db, a, project_id, body.model_dump())


@router.post("/projects/{project_id}/evaluation")
def evaluate_project(
    body: s.EvaluationIn,
    project_id: PathId,
    a: Actor = Depends(require(svc.REVIEW_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(svc.evaluate_project, db, a, project_id, body.model_dump())


# ---------------------------------------------------------------- the caller's own (/me)


@router.get("/me/projects")
def my_projects(include_past: bool = False, a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_projects(db, a, include_past)


@router.get("/me/milestones")
def my_milestones(
    within_days: int = Query(14, ge=1, le=180),
    a: Actor = Depends(require(svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return svc.my_milestones(db, a, within_days)


@router.get("/me/reviews")
def my_reviews(limit: int = LIMIT, a: Actor = Depends(require(svc.GUIDANCE_READ)), db: Session = Depends(get_db)):
    return svc.my_reviews(db, a, limit)
