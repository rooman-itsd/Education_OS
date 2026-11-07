"""HTTP surface of contracts/openapi.yaml. The host app mounts `router` under /api/v1/alumni. Handlers only map HTTP to
the application layer; errors render as {"detail": {"code", "message", "field"?}}."""

from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as p
from ..application import service
from ..application.access import Actor
from ..application.errors import AlumniError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["alumni"])

ALUMNUS_STATUS = "^(active|archived)$"
ASSIGNMENT_STATUS = "^(active|ended)$"
Limit = Query(default=50, ge=1, le=200)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except AlumniError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- directory


@router.get("/directory")
def list_alumni(
    status: str | None = Query(default=None, pattern=ALUMNUS_STATUS),
    is_mentor: bool | None = None,
    graduation_year: int | None = None,
    programme: str | None = Query(default=None, max_length=200),
    q: str | None = Query(default=None, max_length=200),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.DIRECTORY_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "status": status,
        "is_mentor": is_mentor,
        "graduation_year": graduation_year,
        "programme": programme,
        "q": q,
    }
    return _run(service.list_alumni, db, filters, cursor, limit)


@router.post("/directory", status_code=201)
def add_alumnus(body: s.AlumnusInput, a: Actor = Depends(require(p.DIRECTORY_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.add_alumnus, db, a, s.dump(body))


@router.get("/directory/{alumnus_id}")
def get_alumnus(alumnus_id: str, a: Actor = Depends(require(p.DIRECTORY_READ)), db: Session = Depends(get_db)):
    return _run(service.get_alumnus, db, alumnus_id)


@router.put("/directory/{alumnus_id}")
def update_alumnus(
    alumnus_id: str,
    body: s.AlumnusUpdate,
    a: Actor = Depends(require(p.DIRECTORY_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.update_alumnus, db, a, alumnus_id, s.dump(body))


@router.post("/directory/{alumnus_id}/archive")
def archive_alumnus(
    alumnus_id: str,
    body: s.Reason | None = None,
    a: Actor = Depends(require(p.DIRECTORY_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.archive_alumnus, db, a, alumnus_id, body.reason if body else None)


@router.post("/directory/{alumnus_id}/restore")
def restore_alumnus(alumnus_id: str, a: Actor = Depends(require(p.DIRECTORY_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.restore_alumnus, db, a, alumnus_id)


# ---------------------------------------------------------------- mentoring assignments


@router.get("/mentoring/assignments")
def list_assignments(
    status: str | None = Query(default=None, pattern=ASSIGNMENT_STATUS),
    mentor_id: str | None = Query(default=None, max_length=36),
    student_id: str | None = Query(default=None, max_length=36),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.MENTORING_READ)),
    db: Session = Depends(get_db),
):
    filters = {"status": status, "mentor_id": mentor_id, "student_id": student_id}
    return _run(service.list_assignments, db, filters, cursor, limit)


@router.post("/mentoring/assignments", status_code=201)
def start_assignment(
    body: s.AssignmentInput, a: Actor = Depends(require(p.MENTORING_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.start_assignment, db, a, s.dump(body))


@router.get("/mentoring/assignments/{assignment_id}")
def get_assignment(assignment_id: str, a: Actor = Depends(require(p.MENTORING_READ)), db: Session = Depends(get_db)):
    return _run(service.get_assignment, db, assignment_id)


@router.post("/mentoring/assignments/{assignment_id}/end")
def end_assignment(
    assignment_id: str,
    body: s.EndInput | None = None,
    a: Actor = Depends(require(p.MENTORING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.end_assignment, db, a, assignment_id, s.dump(body) if body else {})


@router.get("/mentoring/assignments/{assignment_id}/sessions")
def list_sessions(
    assignment_id: str,
    limit: int = Limit,
    a: Actor = Depends(require(p.MENTORING_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_sessions, db, assignment_id, limit)


@router.post("/mentoring/assignments/{assignment_id}/sessions", status_code=201)
def schedule_session(
    assignment_id: str,
    body: s.SessionInput,
    a: Actor = Depends(require(p.MENTORING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.schedule_session, db, a, assignment_id, s.dump(body))


# ---------------------------------------------------------------- sessions


@router.put("/mentoring/sessions/{session_id}")
def update_session(
    session_id: str,
    body: s.SessionInput,
    a: Actor = Depends(require(p.MENTORING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.update_session, db, a, session_id, s.dump(body))


@router.post("/mentoring/sessions/{session_id}/complete")
def complete_session(
    session_id: str,
    body: s.CompleteInput | None = None,
    a: Actor = Depends(require(p.MENTORING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.complete_session, db, a, session_id, body.notes if body else None)


@router.post("/mentoring/sessions/{session_id}/cancel")
def cancel_session(
    session_id: str,
    body: s.Reason | None = None,
    a: Actor = Depends(require(p.MENTORING_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.cancel_session, db, a, session_id, body.reason if body else None)


# ---------------------------------------------------------------- the caller's own


@router.get("/me/mentoring")
def my_mentoring(a: Actor = Depends(require(p.SELF_READ)), db: Session = Depends(get_db)):
    return _run(service.my_mentoring, db, a)
