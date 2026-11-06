"""HTTP surface for scheduled classes, attendance sessions and records, reports and the `/me` widget reads
(contracts/openapi.yaml). api/router.py includes `router`, so the host mounts these under
/api/v1/timetable-attendance with the timetable operations. Each route requires the operation's x-permission; the
scope a further key widens (own class, `override`, `report:read-all`) is checked by the use cases. Errors follow
api/router.py: a use-case refusal is HTTPException(status, {code, message, details}), and bodies are read as objects
and checked by the use cases, so a malformed body is the contract's 400 with a code."""

from __future__ import annotations

from typing import Any

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import access as k
from ..application import classes as cls
from ..application import reports as rp
from ..application.access import Actor
from ..application.errors import TimetableAttendanceError
from .deps import require

router = APIRouter(tags=["timetable-attendance"])

LIMIT = Query(50, ge=1, le=200)
OFFSET = Query(0, ge=0)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except TimetableAttendanceError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- scheduled classes


@router.get("/scheduled-classes")
def list_scheduled_classes(
    date_from: str | None = None,
    date_to: str | None = None,
    academic_period_id: str | None = None,
    course_offering_id: str | None = None,
    section_id: str | None = None,
    instructor_id: str | None = None,
    department_id: str | None = None,
    timetable_id: str | None = None,
    status: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    _: Actor = Depends(require(k.SCHEDULED_CLASS_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "date_from": date_from,
        "date_to": date_to,
        "academic_period_id": academic_period_id,
        "course_offering_id": course_offering_id,
        "section_id": section_id,
        "instructor_id": instructor_id,
        "department_id": department_id,
        "timetable_id": timetable_id,
        "status": status,
    }
    return _run(cls.list_classes, db, filters, limit, offset)


@router.post("/scheduled-classes", status_code=201)
def create_scheduled_class(
    body: Any = Body(...), a: Actor = Depends(require(k.SCHEDULED_CLASS_WRITE)), db: Session = Depends(get_db)
):
    return _run(cls.create_class, db, a, body)


@router.get("/scheduled-classes/{scheduled_class_id}")
def get_scheduled_class(
    scheduled_class_id: str, _: Actor = Depends(require(k.SCHEDULED_CLASS_READ)), db: Session = Depends(get_db)
):
    return _run(cls.get_class, db, scheduled_class_id)


@router.patch("/scheduled-classes/{scheduled_class_id}")
def update_scheduled_class(
    scheduled_class_id: str,
    body: Any = Body(...),
    a: Actor = Depends(require(k.SCHEDULED_CLASS_WRITE)),
    db: Session = Depends(get_db),
):
    return _run(cls.update_class, db, a, scheduled_class_id, body)


@router.post("/scheduled-classes/{scheduled_class_id}/cancel")
def cancel_scheduled_class(
    scheduled_class_id: str,
    body: Any = Body(None),
    a: Actor = Depends(require(k.SCHEDULED_CLASS_CANCEL)),
    db: Session = Depends(get_db),
):
    return _run(cls.cancel_class, db, a, scheduled_class_id, body)


# ---------------------------------------------------------------- attendance sessions


@router.get("/scheduled-classes/{scheduled_class_id}/attendance-session")
def get_attendance_session_for_class(
    scheduled_class_id: str, a: Actor = Depends(require(k.ATTENDANCE_SESSION_READ)), db: Session = Depends(get_db)
):
    return _run(cls.get_session_of_class, db, a, scheduled_class_id)


@router.post("/scheduled-classes/{scheduled_class_id}/attendance-session")
def open_attendance_session(
    scheduled_class_id: str,
    response: Response,
    a: Actor = Depends(require(k.ATTENDANCE_SESSION_OPEN)),
    db: Session = Depends(get_db),
):
    body, created = _run(cls.open_session, db, a, scheduled_class_id)
    response.status_code = 201 if created else 200
    return body


@router.get("/attendance-sessions/{attendance_session_id}")
def get_attendance_session(
    attendance_session_id: str, a: Actor = Depends(require(k.ATTENDANCE_SESSION_READ)), db: Session = Depends(get_db)
):
    return _run(cls.get_session, db, a, attendance_session_id)


@router.post("/attendance-sessions/{attendance_session_id}/close")
def close_attendance_session(
    attendance_session_id: str, a: Actor = Depends(require(k.ATTENDANCE_SESSION_CLOSE)), db: Session = Depends(get_db)
):
    return _run(cls.close_session, db, a, attendance_session_id)


# ---------------------------------------------------------------- attendance records


@router.get("/attendance-sessions/{attendance_session_id}/records")
def list_attendance_records(
    attendance_session_id: str,
    status: str | None = None,
    a: Actor = Depends(require(k.ATTENDANCE_RECORD_READ)),
    db: Session = Depends(get_db),
):
    return _run(cls.list_records, db, a, attendance_session_id, status)


@router.put("/attendance-sessions/{attendance_session_id}/records")
def mark_attendance(
    attendance_session_id: str,
    body: Any = Body(...),
    a: Actor = Depends(require(k.ATTENDANCE_RECORD_MARK)),
    db: Session = Depends(get_db),
):
    return _run(cls.mark, db, a, attendance_session_id, body)


@router.patch("/attendance-records/{attendance_record_id}")
def correct_attendance_record(
    attendance_record_id: str,
    body: Any = Body(...),
    a: Actor = Depends(require(k.ATTENDANCE_RECORD_CORRECT)),
    db: Session = Depends(get_db),
):
    return _run(cls.correct, db, a, attendance_record_id, body)


@router.get("/attendance-records/{attendance_record_id}/history")
def get_attendance_record_history(
    attendance_record_id: str, a: Actor = Depends(require(k.ATTENDANCE_RECORD_READ)), db: Session = Depends(get_db)
):
    return _run(cls.record_history, db, a, attendance_record_id)


# ---------------------------------------------------------------- reports


@router.get("/reports/students/{student_id}/attendance-summary")
def get_student_attendance_summary(
    student_id: str,
    academic_period_id: str | None = None,
    a: Actor = Depends(require(k.REPORT_READ_DEPARTMENT)),
    db: Session = Depends(get_db),
):
    return _run(rp.student_summary, db, a, student_id, academic_period_id)


@router.get("/reports/students/{student_id}/attendance-history")
def get_student_attendance_history(
    student_id: str,
    academic_period_id: str | None = None,
    course_offering_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(k.REPORT_READ_DEPARTMENT)),
    db: Session = Depends(get_db),
):
    filters = {
        "academic_period_id": academic_period_id,
        "course_offering_id": course_offering_id,
        "date_from": date_from,
        "date_to": date_to,
    }
    return _run(rp.student_history, db, a, student_id, filters, limit, offset)


@router.get("/reports/department-attendance")
def get_department_attendance(
    department_id: str | None = None,
    academic_period_id: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    include_students_below_threshold: str | None = None,
    a: Actor = Depends(require(k.REPORT_READ_DEPARTMENT)),
    db: Session = Depends(get_db),
):
    return _run(
        rp.department_attendance,
        db,
        a,
        department_id,
        academic_period_id,
        date_from,
        date_to,
        include_students_below_threshold,
    )


@router.post("/reports/attendance-eligibility")
def get_attendance_for_eligibility(
    body: Any = Body(...), a: Actor = Depends(require(k.REPORT_READ_ELIGIBILITY)), db: Session = Depends(get_db)
):
    return _run(rp.eligibility, db, a, body)


# ---------------------------------------------------------------- the caller's own (widgets)


@router.get("/me/teaching-schedule")
def get_my_teaching_schedule(
    date: str | None = None, a: Actor = Depends(require(k.SCHEDULED_CLASS_READ)), db: Session = Depends(get_db)
):
    return _run(cls.teaching_schedule, db, a, date)


@router.get("/me/attendance-to-mark")
def get_my_attendance_to_mark(a: Actor = Depends(require(k.ATTENDANCE_RECORD_MARK)), db: Session = Depends(get_db)):
    return _run(cls.attendance_to_mark, db, a)


@router.get("/me/schedule")
def get_my_schedule(
    date: str | None = None, a: Actor = Depends(require(k.SCHEDULED_CLASS_READ_OWN)), db: Session = Depends(get_db)
):
    return _run(cls.my_schedule, db, a, date)


@router.get("/me/attendance-summary")
def get_my_attendance_summary(
    academic_period_id: str | None = None,
    a: Actor = Depends(require(k.REPORT_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(rp.my_summary, db, a, academic_period_id)


@router.get("/me/attendance-history")
def get_my_attendance_history(
    academic_period_id: str | None = None,
    course_offering_id: str | None = None,
    limit: int = LIMIT,
    offset: int = OFFSET,
    a: Actor = Depends(require(k.ATTENDANCE_RECORD_READ_OWN)),
    db: Session = Depends(get_db),
):
    return _run(rp.my_history, db, a, academic_period_id, course_offering_id, limit, offset)
