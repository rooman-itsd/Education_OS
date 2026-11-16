"""FR-11, the system's half: an attendance session still open when its marking window ends is closed at the deadline,
by the scheduler job `timetable-attendance.close-expired-sessions` (entry point `eos.scheduler_jobs`, platform/scheduler).

The job is organisation-scoped: the scheduler fires it once per organisation that has a schedule for it, and hands it
over as `scheduler.job.due` (payload `job`, `run_id`, ...). The handler closes that organisation's due sessions and
reports the outcome with `timetable-attendance.job.finished` (payload `run_id`, `outcome` succeeded|failed, `detail`).

Closing is the same change as `classes.close_session` makes (unmarked eligible students become absent, the class
becomes completed, `attendance-session.closed` is published, one audit entry), with two differences that keep it from
calling that use case: it is the system acting, so there is no actor (`closed_by` is null, the event and audit entry
have no actor, no permission is checked), and it closes many sessions, each in its own savepoint. The decision itself
(`attendance.plan_close`, `attendance.is_due_for_auto_close`) is the domain's.

Delivery is at-least-once, so the job is idempotent twice over: a session that is no longer open is never selected (and
is re-checked under its row lock, so a manual close racing the job wins and the job skips it), and the delivery itself is
recorded in `processed_event` like every other consumed event."""

from __future__ import annotations

import logging
from datetime import datetime

from eos_core import events
from sqlalchemy.orm import Session

from ..domain import attendance as at
from ..domain import classes as cl
from ..infrastructure import attendance_repository as ar
from ..infrastructure import repository as repo
from ..infrastructure.models import AttendanceSessionRow, as_utc
from . import service as svc
from .classes import counts_of, iso, session_domain

log = logging.getLogger("eos.timetable_attendance")

JOB_KEY = "timetable-attendance.close-expired-sessions"
JOB_FINISHED = f"{svc.MODULE}.job.finished"
SUCCEEDED, FAILED = "succeeded", "failed"

# Registered in pyproject.toml under `eos.scheduler_jobs` (platform/scheduler/README.md). The scheduler seeds a default
# schedule only for platform jobs, so none is declared: an operator schedules this job per organisation, and how often
# is theirs to choose (a session closes at its deadline at the next run after it).
JOBS = {
    JOB_KEY: {
        "scope": "organisation",
        "idempotent": True,
        "description": "Attendance sessions still open after their marking deadline are closed by the system: "
        "unmarked students become absent and attendance-session.closed is published, once per session.",
    },
}


def _close(db: Session, organisation_id: str, session_id: str, now: datetime) -> bool:
    """Close one session as the system. False when it is no longer due (closed, cancelled or not yet past its
    deadline by the time its row is locked), so the caller counts only what this call closed."""
    session = ar.session(db, session_id, lock=True)
    if session is None or not at.is_due_for_auto_close(session_domain(session), now):
        return False
    row = ar.scheduled_class(db, session.scheduled_class_id, lock=True)
    records = ar.records_of_session(db, session.id)
    closed, unmarked = at.plan_close(
        session_domain(session),
        [r.student_id for r in records],
        {r.student_id: r.status for r in records if r.status},
        now=now,
        closed_by=None,
    )
    absent = set(unmarked)
    for r in records:
        if r.student_id in absent:
            r.status, r.marked_at = at.ABSENT, now
    session.status, session.closed_at, session.closed_by = closed.status, closed.closed_at, closed.closed_by
    row.status = cl.COMPLETED
    final = counts_of(records)
    events.publish(
        db,
        f"{svc.MODULE}.attendance-session.closed",
        organisation_id,
        {
            "organisation_id": organisation_id,
            "attendance_session_id": session.id,
            "scheduled_class_id": row.id,
            "course_offering_id": row.course_offering_id,
            "section_id": row.section_id,
            "class_date": iso(row.class_date),
            "closed_by": closed.closed_by,
            "closed_at": iso(now),
            **{s: final[s] for s in at.ATTENDANCE_STATUSES},
        },
    )
    svc._audit(
        db,
        None,
        "attendance-session.closed",
        "attendance_session",
        session,
        before={"status": at.OPEN},
        after={"status": at.CLOSED, "marked_absent_at_close": len(absent), **final},
    )
    return True


def close_expired_sessions(db: Session, organisation_id: str) -> tuple[int, int]:
    """Close the organisation's open sessions whose marking deadline has passed. Returns (closed, failed). Each
    session is closed in its own savepoint: one that fails leaves nothing behind (no absent mark, event or audit
    entry) and does not stop the others; it stays open and the next run tries it again. The caller commits."""
    now = as_utc(svc.clock())
    due: list[AttendanceSessionRow] = repo.expired_open_sessions(db, now)
    closed = failed = 0
    for session_id in [s.id for s in due]:
        try:
            with db.begin_nested():
                closed += _close(db, organisation_id, session_id, now)
        except Exception:  # noqa: BLE001 - the savepoint is rolled back; the error class is logged, not its text
            db.expire_all()
            failed += 1
            log.exception("timetable-attendance: could not close attendance session %s", session_id)
    return closed, failed


def run(db: Session, organisation_id: str, payload: dict, occurred_at: datetime) -> str:
    """The job: close what is due, then report the run so the scheduler can close it."""
    closed, failed = close_expired_sessions(db, organisation_id)
    detail = f"{closed} attendance session(s) closed"
    if failed:
        detail += f"; {failed} could not be closed and stay open for the next run"
    events.publish(
        db,
        JOB_FINISHED,
        organisation_id,
        {"run_id": payload.get("run_id"), "outcome": FAILED if failed else SUCCEEDED, "detail": detail},
    )
    return "applied"
