"""HTTP surface of timetable-attendance, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/timetable-attendance. Handlers only map HTTP to the use cases in application/service.py.

Errors follow the repository's current convention (academic-management, facility-booking, hostel): a use-case refusal
becomes HTTPException(status, {code, message, details}), which FastAPI wraps as {"detail": ...}. Request bodies are
read as objects and checked by the use cases, so a malformed body is the contract's 400 with a code, not FastAPI's 422.

This batch serves the timetable operations: listTimetables, createTimetable, getTimetable, updateTimetable,
replaceTimetableSlots and listTimetableConflicts, and publishTimetable and unpublishTimetable. The other operations of
the contract are added with their use cases."""

from __future__ import annotations

from typing import Any

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as k
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import TimetableAttendanceError
from . import classes_attendance
from .deps import require

router = APIRouter(tags=["timetable-attendance"])
# Scheduled classes, attendance sessions and records, reports and the /me widget reads (api/classes_attendance.py). Its
# routes join this router as they are (no prefix, no extra dependency), so the host and the tests see one flat router.
router.routes.extend(classes_attendance.router.routes)

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TimetableAttendanceError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- timetables


@router.get("/timetables")
def list_timetables(
    academic_period_id: str | None = None,
    department_id: str | None = None,
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.TIMETABLE_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_timetables, db, academic_period_id, department_id, status, limit, offset)


@router.post("/timetables", status_code=201)
def create_timetable(
    body: dict = Body(...), a: Actor = Depends(require(k.TIMETABLE_WRITE)), db: Session = Depends(get_db)
):
    return _run(svc.create_timetable, db, a, body)


@router.get("/timetables/{timetable_id}")
def get_timetable(timetable_id: str, _: Actor = Depends(require(k.TIMETABLE_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_timetable, db, timetable_id)


@router.patch("/timetables/{timetable_id}")
def update_timetable(
    timetable_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.TIMETABLE_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_timetable, db, a, timetable_id, body)


@router.put("/timetables/{timetable_id}/slots")
def replace_timetable_slots(
    timetable_id: str,
    body: dict = Body(...),
    a: Actor = Depends(require(k.TIMETABLE_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(svc.replace_slots, db, a, timetable_id, body)


@router.get("/timetables/{timetable_id}/conflicts")
def list_timetable_conflicts(
    timetable_id: str, _: Actor = Depends(require(k.TIMETABLE_READ)), db: Session = Depends(get_db)
):
    return _run(svc.timetable_conflicts, db, timetable_id)


@router.post("/timetables/{timetable_id}/publish")
def publish_timetable(
    timetable_id: str, a: Actor = Depends(require(k.TIMETABLE_PUBLISH)), db: Session = Depends(get_db)
):
    return _run(svc.publish_timetable, db, a, timetable_id)


@router.post("/timetables/{timetable_id}/unpublish")
def unpublish_timetable(
    timetable_id: str,
    body: Any = Body(None),
    a: Actor = Depends(require(k.TIMETABLE_PUBLISH)),
    db: Session = Depends(get_db),
):
    return _run(svc.unpublish_timetable, db, a, timetable_id, body)
