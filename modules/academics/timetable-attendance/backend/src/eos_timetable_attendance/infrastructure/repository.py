"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath; on SQLite, which has none, `q` is what keeps a query inside the organisation, so no query
in this module is written without it."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..domain.values import DAYS_OF_WEEK
from .models import (
    AssignmentRef,
    AttendanceSessionRow,
    AuditEntry,
    OfferingRef,
    ScheduledClassRow,
    SectionRef,
    TermRef,
    TimetableRow,
    TimetableSlotRow,
)


def q(db: Session, model) -> Select:
    """`select(model)` limited to the session's organisation. With no organisation on the session it matches nothing."""
    return scoped(db, select(model), model)


def get(db: Session, model, row_id: str):
    """One row of the caller's organisation by id, or None (another organisation's row is not found)."""
    return db.scalars(q(db, model).where(model.id == row_id)).first()


# Constraint name -> (table, columns), for telling a conflict the module answers with 409 from any other integrity error.
SLOT_DATE_CONSTRAINTS = {
    "uq_timetable_attendance_class_slot_date": (
        "timetable_attendance_scheduled_class",
        ("organisation_id", "slot_id", "class_date"),
    ),
}
SESSION_CLASS_CONSTRAINTS = {
    "uq_timetable_attendance_session_class": (
        "timetable_attendance_attendance_session",
        ("organisation_id", "scheduled_class_id"),
    ),
}
RECORD_STUDENT_CONSTRAINTS = {
    "uq_timetable_attendance_record_student": (
        "timetable_attendance_attendance_record",
        ("organisation_id", "attendance_session_id", "student_id"),
    ),
}
PROCESSED_EVENT_CONSTRAINTS = {
    "uq_timetable_attendance_processed_event": (
        "timetable_attendance_processed_event",
        ("organisation_id", "event_id"),
    ),
}
# One audit record per client_token (platform/audit NewRecord: a replayed token returns the original record).
AUDIT_TOKEN_CONSTRAINTS = {
    "uq_timetable_attendance_audit_client_token": (
        "timetable_attendance_audit_entry",
        ("organisation_id", "client_token"),
    ),
}


def _violates(err: IntegrityError, constraints: dict[str, tuple[str, tuple[str, ...]]]) -> bool:
    """True only when `err` is a violation of one of `constraints`. PostgreSQL names the constraint (psycopg
    `diag.constraint_name`); SQLite names its columns ("UNIQUE constraint failed: t.a, t.b"). Any other integrity
    error (another constraint, a foreign key, a NOT NULL) does not count."""
    orig = err.orig
    name = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if name:
        return name in constraints
    message = str(orig)
    return any(
        message == "UNIQUE constraint failed: " + ", ".join(f"{table}.{column}" for column in columns)
        for table, columns in constraints.values()
    )


def is_slot_date_conflict(err: IntegrityError) -> bool:
    """A class already exists for this slot and date (two generations racing), and nothing else."""
    return _violates(err, SLOT_DATE_CONSTRAINTS)


def is_session_conflict(err: IntegrityError) -> bool:
    """The class already has an attendance session (two opens racing), and nothing else."""
    return _violates(err, SESSION_CLASS_CONSTRAINTS)


def is_record_conflict(err: IntegrityError) -> bool:
    """The student already has a record in the session, and nothing else."""
    return _violates(err, RECORD_STUDENT_CONSTRAINTS)


def is_processed_event_conflict(err: IntegrityError) -> bool:
    """This envelope id is already recorded for the organisation (two deliveries racing), and nothing else."""
    return _violates(err, PROCESSED_EVENT_CONSTRAINTS)


def is_audit_token_conflict(err: IntegrityError) -> bool:
    """An audit record with this client_token already exists in the organisation, and nothing else."""
    return _violates(err, AUDIT_TOKEN_CONSTRAINTS)


def audit_entry_by_token(db: Session, organisation_id: str, client_token: str) -> AuditEntry | None:
    query = q(db, AuditEntry).where(
        AuditEntry.organisation_id == organisation_id, AuditEntry.client_token == client_token
    )
    return db.scalars(query).first()


# ---------------------------------------------------------------- timetables


def timetables(
    db: Session, academic_period_id: str | None, department_id: str | None, status: str | None, limit: int, offset: int
) -> tuple[list[TimetableRow], int]:
    """A page of the organisation's timetables ordered by name, and the total that match."""
    query = q(db, TimetableRow)
    if academic_period_id:
        query = query.where(TimetableRow.academic_period_id == academic_period_id)
    if department_id:
        query = query.where(TimetableRow.department_id == department_id)
    if status:
        query = query.where(TimetableRow.status == status)
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(TimetableRow.name, TimetableRow.id).limit(limit).offset(offset))
    return list(rows), total


def timetable_for_update(db: Session, timetable_id: str) -> TimetableRow | None:
    """The timetable, locked until the transaction ends on PostgreSQL, so two changes to one timetable queue up
    instead of interleaving. SQLite has no row locks; its writers are serialised by the database itself."""
    return db.scalars(q(db, TimetableRow).where(TimetableRow.id == timetable_id).with_for_update()).first()


def slot_counts(db: Session, timetable_ids: list[str]) -> dict[str, int]:
    if not timetable_ids:
        return {}
    query = q(db, TimetableSlotRow).with_only_columns(TimetableSlotRow.timetable_id, func.count())
    rows = db.execute(
        query.where(TimetableSlotRow.timetable_id.in_(timetable_ids)).group_by(TimetableSlotRow.timetable_id)
    )
    return {timetable_id: count for timetable_id, count in rows}


def slots_of(db: Session, timetable_id: str) -> list[TimetableSlotRow]:
    rows = db.scalars(q(db, TimetableSlotRow).where(TimetableSlotRow.timetable_id == timetable_id))
    return sorted(rows, key=lambda r: (DAYS_OF_WEEK.index(r.day_of_week), r.start_time, r.id))


def published_slots_in_period(
    db: Session, academic_period_id: str, exclude_timetable_id: str
) -> list[tuple[str, TimetableSlotRow]]:
    """(timetable id, slot) of every other published timetable of the period (FR-4)."""
    ids = list(
        db.scalars(
            q(db, TimetableRow)
            .with_only_columns(TimetableRow.id)
            .where(
                TimetableRow.academic_period_id == academic_period_id,
                TimetableRow.status == "published",
                TimetableRow.id != exclude_timetable_id,
            )
        )
    )
    if not ids:
        return []
    rows = db.scalars(q(db, TimetableSlotRow).where(TimetableSlotRow.timetable_id.in_(ids)))
    return [(r.timetable_id, r) for r in rows]


def classes_of_timetable(db: Session, timetable_id: str) -> list[ScheduledClassRow]:
    """Every scheduled class generated from the timetable, earliest first."""
    rows = db.scalars(q(db, ScheduledClassRow).where(ScheduledClassRow.timetable_id == timetable_id))
    return sorted(rows, key=lambda r: (r.starts_at, r.id))


def class_ids_with_session(db: Session, class_ids: list[str]) -> set[str]:
    """Of these classes, the ids of those that have an attendance session (open or closed)."""
    if not class_ids:
        return set()
    query = q(db, AttendanceSessionRow).with_only_columns(AttendanceSessionRow.scheduled_class_id)
    return set(db.scalars(query.where(AttendanceSessionRow.scheduled_class_id.in_(class_ids))))


def expired_open_sessions(db: Session, now) -> list[AttendanceSessionRow]:
    """FR-11: the organisation's attendance sessions still open after their marking deadline, earliest deadline first.
    A closed or cancelled session is never returned."""
    query = q(db, AttendanceSessionRow).where(
        AttendanceSessionRow.status == "open", AttendanceSessionRow.marking_deadline < now
    )
    return list(db.scalars(query.order_by(AttendanceSessionRow.marking_deadline, AttendanceSessionRow.id)))


# ---------------------------------------------------------------- read models (filled from consumed events)


def term_ref(db: Session, academic_period_id: str) -> TermRef | None:
    """The known term for an academic period, or None (its `term.created` event has not been consumed)."""
    return db.scalars(q(db, TermRef).where(TermRef.academic_period_id == academic_period_id)).first()


def offering_refs(db: Session, ids: set[str]) -> dict[str, OfferingRef]:
    if not ids:
        return {}
    # a row whose creation event has not arrived yet (academic_period_id is NULL) is not known
    query = q(db, OfferingRef).where(
        OfferingRef.course_offering_id.in_(ids), OfferingRef.academic_period_id.is_not(None)
    )
    return {r.course_offering_id: r for r in db.scalars(query)}


def section_refs(db: Session, ids: set[str]) -> dict[str, SectionRef]:
    if not ids:
        return {}
    # a row whose creation event has not arrived yet (code is NULL) is not known
    query = q(db, SectionRef).where(SectionRef.section_id.in_(ids), SectionRef.code.is_not(None))
    return {r.section_id: r for r in db.scalars(query)}


def assignment_refs(db: Session, ids: set[str]) -> dict[str, AssignmentRef]:
    if not ids:
        return {}
    rows = db.scalars(q(db, AssignmentRef).where(AssignmentRef.instructor_assignment_id.in_(ids)))
    return {r.instructor_assignment_id: r for r in rows}


def ref_row(db: Session, model, column, value: str, organisation_id: str):
    """The read-model row with this key in this organisation, or None. The organisation is named as well as scoped,
    so a handler never reads a row of another organisation even if the session scope were wrong."""
    return db.scalars(q(db, model).where(column == value, model.organisation_id == organisation_id)).first()
