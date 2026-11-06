"""HTTP surface of examinations, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/examinations (enabling the module in the application configuration is not part of this change). Handlers only
map HTTP to the use cases in application/service.py.

Errors follow the repository's convention: a use-case refusal becomes HTTPException(status, {code, message, details}),
which FastAPI wraps as {"detail": ...}. Request bodies are read as objects and checked by the use cases, so a
malformed body is the contract's 400 with a code, not FastAPI's 422.

This batch serves the configuration and exam-cycle operations: listGradingSchemes, createGradingScheme,
getGradingScheme, replaceGradingScheme, setDefaultGradingScheme, listAssessmentSchemes, createAssessmentScheme,
getAssessmentScheme, replaceAssessmentScheme, activateAssessmentScheme, listExamCycles, createExamCycle, getExamCycle,
updateExamCycle and changeExamCycleStatus; and the paper and session operations: listExamPapers, createExamPapers,
getExamPaper, updateExamPaper, listExamSessions, scheduleExamSession, getExamSession, rescheduleExamSession and
cancelExamSession."""

from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as k
from ..application import schedule as sch
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import ExaminationsError
from .deps import require

router = APIRouter(tags=["examinations"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)

# x-permission is the narrowest key; the wider key of the same action is accepted too (contracts/permissions.yaml).
ASSESSMENT_WRITE = require(k.ASSESSMENT_SCHEME_WRITE_DEPARTMENT, k.ASSESSMENT_SCHEME_WRITE_ALL)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ExaminationsError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- exam cycles


@router.get("/exam-cycles")
def list_exam_cycles(
    academic_period_id: str | None = None,
    status: str | None = None,
    cycle_type: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.EXAM_CYCLE_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_exam_cycles, db, academic_period_id, status, cycle_type, limit, offset)


@router.post("/exam-cycles", status_code=201)
def create_exam_cycle(
    body: dict = Body(...), a: Actor = Depends(require(k.EXAM_CYCLE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.create_exam_cycle, db, a, body)


@router.get("/exam-cycles/{exam_cycle_id}")
def get_exam_cycle(exam_cycle_id: str, _: Actor = Depends(require(k.EXAM_CYCLE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_exam_cycle, db, exam_cycle_id)


@router.patch("/exam-cycles/{exam_cycle_id}")
def update_exam_cycle(
    exam_cycle_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.EXAM_CYCLE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_exam_cycle, db, a, exam_cycle_id, body)


@router.post("/exam-cycles/{exam_cycle_id}/status")
def change_exam_cycle_status(
    exam_cycle_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.EXAM_CYCLE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.change_exam_cycle_status, db, a, exam_cycle_id, body)


# ---------------------------------------------------------------- assessment schemes


@router.get("/assessment-schemes")
def list_assessment_schemes(
    course_offering_id: str | None = None,
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.ASSESSMENT_SCHEME_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_assessment_schemes, db, course_offering_id, status, limit, offset)


@router.post("/assessment-schemes", status_code=201)
def create_assessment_scheme(
    body: dict = Body(...), a: Actor = Depends(ASSESSMENT_WRITE), db: Session = Depends(get_db)
):
    return _run(svc.create_assessment_scheme, db, a, body)


@router.get("/assessment-schemes/{assessment_scheme_id}")
def get_assessment_scheme(
    assessment_scheme_id: str, _: Actor = Depends(require(k.ASSESSMENT_SCHEME_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_assessment_scheme, db, assessment_scheme_id)


@router.put("/assessment-schemes/{assessment_scheme_id}")
def replace_assessment_scheme(
    assessment_scheme_id: str,
    body: dict = Body(...),
    a: Actor = Depends(ASSESSMENT_WRITE),
    db: Session = Depends(get_db),
):
    return _run(svc.replace_assessment_scheme, db, a, assessment_scheme_id, body)


@router.post("/assessment-schemes/{assessment_scheme_id}/activate")
def activate_assessment_scheme(
    assessment_scheme_id: str, a: Actor = Depends(ASSESSMENT_WRITE), db: Session = Depends(get_db)
):
    return _run(svc.activate_assessment_scheme, db, a, assessment_scheme_id)


# ---------------------------------------------------------------- grading schemes


@router.get("/grading-schemes")
def list_grading_schemes(_: Actor = Depends(require(k.GRADING_SCHEME_READ)), db: Session = Depends(get_db)):
    return _run(svc.list_grading_schemes, db)


@router.post("/grading-schemes", status_code=201)
def create_grading_scheme(
    body: dict = Body(...), a: Actor = Depends(require(k.GRADING_SCHEME_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.create_grading_scheme, db, a, body)


@router.get("/grading-schemes/{grading_scheme_id}")
def get_grading_scheme(
    grading_scheme_id: str, _: Actor = Depends(require(k.GRADING_SCHEME_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_grading_scheme, db, grading_scheme_id)


@router.put("/grading-schemes/{grading_scheme_id}")
def replace_grading_scheme(
    grading_scheme_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.GRADING_SCHEME_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.replace_grading_scheme, db, a, grading_scheme_id, body)


@router.post("/grading-schemes/{grading_scheme_id}/set-default")
def set_default_grading_scheme(
    grading_scheme_id: str, a: Actor = Depends(require(k.GRADING_SCHEME_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.set_default_grading_scheme, db, a, grading_scheme_id)


# ---------------------------------------------------------------- papers


@router.get("/papers")
def list_exam_papers(
    exam_cycle_id: str | None = None,
    course_offering_id: str | None = None,
    department_id: str | None = None,
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.PAPER_READ)),
    db: Session = Depends(get_db),
):
    return _run(sch.list_exam_papers, db, exam_cycle_id, course_offering_id, department_id, status, limit, offset)


@router.post("/papers", status_code=201)
def create_exam_papers(
    body: dict = Body(...), a: Actor = Depends(require(k.PAPER_MANAGE)), db: Session = Depends(get_db)
):
    return _run(sch.create_exam_papers, db, a, body)


@router.get("/papers/{exam_paper_id}")
def get_exam_paper(exam_paper_id: str, _: Actor = Depends(require(k.PAPER_READ)), db: Session = Depends(get_db)):
    return _run(sch.get_exam_paper, db, exam_paper_id)


@router.patch("/papers/{exam_paper_id}")
def update_exam_paper(
    exam_paper_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.PAPER_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(sch.update_exam_paper, db, a, exam_paper_id, body)


# ---------------------------------------------------------------- sessions


@router.get("/sessions")
def list_exam_sessions(
    exam_cycle_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    course_offering_id: str | None = None,
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.SESSION_READ)),
    db: Session = Depends(get_db),
):
    return _run(
        sch.list_exam_sessions, db, exam_cycle_id, date_from, date_to, course_offering_id, status, limit, offset
    )


@router.post("/sessions", status_code=201)
def schedule_exam_session(
    body: dict = Body(...), a: Actor = Depends(require(k.SESSION_MANAGE)), db: Session = Depends(get_db)
):
    return _run(sch.schedule_exam_session, db, a, body)


@router.get("/sessions/{exam_session_id}")
def get_exam_session(exam_session_id: str, _: Actor = Depends(require(k.SESSION_READ)), db: Session = Depends(get_db)):
    return _run(sch.get_exam_session, db, exam_session_id)


@router.patch("/sessions/{exam_session_id}")
def reschedule_exam_session(
    exam_session_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.SESSION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(sch.reschedule_exam_session, db, a, exam_session_id, body)


@router.post("/sessions/{exam_session_id}/cancel")
def cancel_exam_session(
    exam_session_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.SESSION_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(sch.cancel_exam_session, db, a, exam_session_id, body)
