"""Queries, always scoped to the caller's organisation (eos_core.db.scoped). On Postgres row-level security enforces
the same rule underneath; on SQLite, which has none, `q` is what keeps a query inside the organisation, so no query
in this module is written without it."""

from __future__ import annotations

from eos_core.db import scoped
from sqlalchemy import Select, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .models import AuditEntry


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


def is_audit_token_conflict(err: IntegrityError) -> bool:
    """An audit record with this client_token already exists in the organisation, and nothing else."""
    return _violates(err, AUDIT_TOKEN_CONSTRAINTS)


def audit_entry_by_token(db: Session, organisation_id: str, client_token: str) -> AuditEntry | None:
    query = q(db, AuditEntry).where(
        AuditEntry.organisation_id == organisation_id, AuditEntry.client_token == client_token
    )
    return db.scalars(query).first()
