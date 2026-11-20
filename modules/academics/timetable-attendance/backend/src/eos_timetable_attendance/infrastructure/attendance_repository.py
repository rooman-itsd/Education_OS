"""Queries for scheduled classes, attendance sessions and records, and the reports over them. Like repository.py,
every query starts from `q` (eos_core.db.scoped), so it stays inside the caller's organisation on SQLite as well as
under Postgres row-level security; a join also names the organisation on both sides."""

from __future__ import annotations

from collections.abc import Collection
from datetime import date, datetime

from sqlalchemy import Select, and_, func, or_, select
from sqlalchemy.orm import Session

from .models import (
    AttendanceRecordChangeRow,
    AttendanceRecordRow,
    AttendanceSessionRow,
    OfferingRef,
    PersonAccount,
    ScheduledClassRow,
    SectionMember,
    SectionRef,
    TermRef,
)
from .repository import q


def _first(db: Session, query: Select):
    return db.scalars(query).first()


def _is(column, value: str | Collection[str]):
    """column equals the id, or is one of the ids (a student's person id and user id, classes.my_student_ids)."""
    if isinstance(value, str):
        return column == value
    return column.in_(sorted(value))


def person_for_user(db: Session, user_id: str) -> str | None:
    """The student-information person a sign-in account is linked to, if a link is known. Two persons can briefly claim
    one account when the events arrive out of order; the later link wins."""
    query = q(db, PersonAccount).where(PersonAccount.identity_user_id == user_id)
    row = _first(db, query.order_by(PersonAccount.linked_as_of.desc(), PersonAccount.id))
    return row.person_id if row is not None else None


# ---------------------------------------------------------------- scheduled classes


def scheduled_class(db: Session, class_id: str, *, lock: bool = False) -> ScheduledClassRow | None:
    """The class, locked until the transaction ends on PostgreSQL when `lock` (two changes to one class queue up)."""
    query = q(db, ScheduledClassRow).where(ScheduledClassRow.id == class_id)
    return _first(db, query.with_for_update() if lock else query)


def classes(
    db: Session,
    *,
    date_from: date | None = None,
    date_to: date | None = None,
    academic_period_id: str | None = None,
    course_offering_id: str | None = None,
    section_id: str | None = None,
    instructor_id: str | None = None,
    offering_ids: set[str] | None = None,
    timetable_id: str | None = None,
    status: str | None = None,
    limit: int,
    offset: int,
) -> tuple[list[ScheduledClassRow], int]:
    """A page of the organisation's classes ordered by start time, and the total that match. `offering_ids` limits
    them to those course offerings (the department filter)."""
    query = q(db, ScheduledClassRow)
    if date_from is not None:
        query = query.where(ScheduledClassRow.class_date >= date_from)
    if date_to is not None:
        query = query.where(ScheduledClassRow.class_date <= date_to)
    for column, value in (
        (ScheduledClassRow.academic_period_id, academic_period_id),
        (ScheduledClassRow.course_offering_id, course_offering_id),
        (ScheduledClassRow.section_id, section_id),
        (ScheduledClassRow.instructor_id, instructor_id),
        (ScheduledClassRow.timetable_id, timetable_id),
        (ScheduledClassRow.status, status),
    ):
        if value is not None:
            query = query.where(column == value)
    if offering_ids is not None:
        query = query.where(ScheduledClassRow.course_offering_id.in_(offering_ids or {""}))
    total = db.scalar(select(func.count()).select_from(query.subquery())) or 0
    rows = db.scalars(query.order_by(ScheduledClassRow.starts_at, ScheduledClassRow.id).limit(limit).offset(offset))
    return list(rows), total


def classes_taught_on(db: Session, instructor_id: str, day: date) -> list[ScheduledClassRow]:
    query = q(db, ScheduledClassRow).where(
        ScheduledClassRow.instructor_id == instructor_id, ScheduledClassRow.class_date == day
    )
    return list(db.scalars(query.order_by(ScheduledClassRow.starts_at, ScheduledClassRow.id)))


def classes_of_sections_on(db: Session, section_ids: set[str], day: date) -> list[ScheduledClassRow]:
    if not section_ids:
        return []
    query = q(db, ScheduledClassRow).where(
        ScheduledClassRow.section_id.in_(section_ids), ScheduledClassRow.class_date == day
    )
    return list(db.scalars(query.order_by(ScheduledClassRow.starts_at, ScheduledClassRow.id)))


def started_classes_taught(
    db: Session, instructor_id: str, now: datetime, ended_after: datetime
) -> list[ScheduledClassRow]:
    """The instructor's scheduled classes that have started by `now` and end after `ended_after`, oldest first."""
    query = q(db, ScheduledClassRow).where(
        ScheduledClassRow.instructor_id == instructor_id,
        ScheduledClassRow.status == "scheduled",
        ScheduledClassRow.starts_at <= now,
        ScheduledClassRow.ends_at >= ended_after,
    )
    return list(db.scalars(query.order_by(ScheduledClassRow.starts_at, ScheduledClassRow.id)))


# ---------------------------------------------------------------- attendance sessions and records


def session(db: Session, session_id: str, *, lock: bool = False) -> AttendanceSessionRow | None:
    query = q(db, AttendanceSessionRow).where(AttendanceSessionRow.id == session_id)
    return _first(db, query.with_for_update() if lock else query)


def session_of_class(db: Session, class_id: str, *, lock: bool = False) -> AttendanceSessionRow | None:
    query = q(db, AttendanceSessionRow).where(AttendanceSessionRow.scheduled_class_id == class_id)
    return _first(db, query.with_for_update() if lock else query)


def sessions_of_classes(db: Session, class_ids: list[str]) -> dict[str, AttendanceSessionRow]:
    """Class id -> its attendance session, for the classes that have one."""
    if not class_ids:
        return {}
    rows = db.scalars(q(db, AttendanceSessionRow).where(AttendanceSessionRow.scheduled_class_id.in_(class_ids)))
    return {r.scheduled_class_id: r for r in rows}


def records_of_session(db: Session, session_id: str) -> list[AttendanceRecordRow]:
    query = q(db, AttendanceRecordRow).where(AttendanceRecordRow.attendance_session_id == session_id)
    return list(db.scalars(query.order_by(AttendanceRecordRow.student_id)))


def records_of_sessions(db: Session, session_ids: list[str]) -> dict[str, list[AttendanceRecordRow]]:
    if not session_ids:
        return {}
    found: dict[str, list[AttendanceRecordRow]] = {s: [] for s in session_ids}
    for r in db.scalars(q(db, AttendanceRecordRow).where(AttendanceRecordRow.attendance_session_id.in_(session_ids))):
        found[r.attendance_session_id].append(r)
    return found


def record(db: Session, record_id: str, *, lock: bool = False) -> AttendanceRecordRow | None:
    query = q(db, AttendanceRecordRow).where(AttendanceRecordRow.id == record_id)
    return _first(db, query.with_for_update() if lock else query)


def corrected_record_ids(db: Session, record_ids: list[str]) -> set[str]:
    if not record_ids:
        return set()
    query = q(db, AttendanceRecordChangeRow).with_only_columns(AttendanceRecordChangeRow.attendance_record_id)
    return set(db.scalars(query.where(AttendanceRecordChangeRow.attendance_record_id.in_(record_ids))))


def changes_of_record(db: Session, record_id: str) -> list[AttendanceRecordChangeRow]:
    query = q(db, AttendanceRecordChangeRow).where(AttendanceRecordChangeRow.attendance_record_id == record_id)
    return list(db.scalars(query.order_by(AttendanceRecordChangeRow.changed_at, AttendanceRecordChangeRow.id)))


# ---------------------------------------------------------------- section membership (read model)


def _member_on(day_from: date, day_to: date):
    """Allocated at some point between the two dates (inclusive)."""
    return and_(
        SectionMember.allocated_from <= day_to,
        or_(SectionMember.allocated_to.is_(None), SectionMember.allocated_to >= day_from),
    )


def members_on(db: Session, section_id: str, day: date) -> list[SectionMember]:
    """FR-7: the students allocated to the section on the date."""
    query = q(db, SectionMember).where(SectionMember.section_id == section_id, _member_on(day, day))
    return list(db.scalars(query.order_by(SectionMember.student_id)))


def sections_of_student_on(db: Session, student_id: str | Collection[str], day: date) -> set[str]:
    query = q(db, SectionMember).with_only_columns(SectionMember.section_id)
    return set(db.scalars(query.where(_is(SectionMember.student_id, student_id), _member_on(day, day))))


def students_in_sections_between(db: Session, section_ids: set[str], first: date | None, last: date) -> set[str]:
    """The students allocated to any of the sections at some point in the range (`first` None: since ever)."""
    if not section_ids:
        return set()
    query = q(db, SectionMember).with_only_columns(SectionMember.student_id)
    query = query.where(SectionMember.section_id.in_(section_ids), _member_on(first or date.min, last))
    return set(db.scalars(query))


def student_names(db: Session, student_ids: set[str]) -> dict[str, str]:
    """The cached display name of each student, when an allocation event carried one (PRD Q3)."""
    if not student_ids:
        return {}
    query = q(db, SectionMember).where(
        SectionMember.student_id.in_(student_ids), SectionMember.student_name.is_not(None)
    )
    rows = db.scalars(query.order_by(SectionMember.allocated_from))
    return {r.student_id: r.student_name for r in rows}  # the latest allocation's name wins


# ---------------------------------------------------------------- read models


def section_refs_any(db: Session, ids: set[str]) -> dict[str, SectionRef]:
    """Known sections by id (for display: their code)."""
    if not ids:
        return {}
    query = q(db, SectionRef).where(SectionRef.section_id.in_(ids), SectionRef.code.is_not(None))
    return {r.section_id: r for r in db.scalars(query)}


def section_ids_of_offering(db: Session, course_offering_id: str) -> set[str]:
    query = q(db, SectionRef).with_only_columns(SectionRef.section_id)
    return set(db.scalars(query.where(SectionRef.course_offering_id == course_offering_id)))


def active_term(db: Session, day: date) -> TermRef | None:
    """The known term whose dates contain the day; the one that started last if several do."""
    query = q(db, TermRef).where(TermRef.starts_on <= day, TermRef.ends_on >= day)
    return _first(db, query.order_by(TermRef.starts_on.desc(), TermRef.id))


def offering_ids_of_department(db: Session, department_id: str, academic_period_id: str | None = None) -> set[str]:
    query = q(db, OfferingRef).with_only_columns(OfferingRef.course_offering_id)
    query = query.where(OfferingRef.department_id == department_id)
    if academic_period_id is not None:
        query = query.where(OfferingRef.academic_period_id == academic_period_id)
    return set(db.scalars(query))


# ---------------------------------------------------------------- reports


def attendance(
    db: Session,
    *,
    session_statuses: tuple[str, ...] = ("closed",),
    academic_period_id: str | None = None,
    course_offering_id: str | None = None,
    offering_ids: set[str] | None = None,
    student_id: str | Collection[str] | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[tuple[AttendanceRecordRow, AttendanceSessionRow, ScheduledClassRow]]:
    """Every record with its session and class, of sessions in `session_statuses` and classes that are not cancelled,
    newest class first."""
    query = (
        q(db, AttendanceRecordRow)
        .add_columns(AttendanceSessionRow, ScheduledClassRow)
        .join(
            AttendanceSessionRow,
            and_(
                AttendanceSessionRow.id == AttendanceRecordRow.attendance_session_id,
                AttendanceSessionRow.organisation_id == AttendanceRecordRow.organisation_id,
            ),
        )
        .join(
            ScheduledClassRow,
            and_(
                ScheduledClassRow.id == AttendanceSessionRow.scheduled_class_id,
                ScheduledClassRow.organisation_id == AttendanceSessionRow.organisation_id,
            ),
        )
        .where(AttendanceSessionRow.status.in_(session_statuses), ScheduledClassRow.status != "cancelled")
    )
    if academic_period_id is not None:
        query = query.where(ScheduledClassRow.academic_period_id == academic_period_id)
    if course_offering_id is not None:
        query = query.where(ScheduledClassRow.course_offering_id == course_offering_id)
    if offering_ids is not None:
        query = query.where(ScheduledClassRow.course_offering_id.in_(offering_ids or {""}))
    if student_id is not None:
        query = query.where(_is(AttendanceRecordRow.student_id, student_id))
    if date_from is not None:
        query = query.where(ScheduledClassRow.class_date >= date_from)
    if date_to is not None:
        query = query.where(ScheduledClassRow.class_date <= date_to)
    query = query.order_by(ScheduledClassRow.starts_at.desc(), ScheduledClassRow.id, AttendanceRecordRow.student_id)
    return [(r, s, c) for r, s, c in db.execute(query)]


def open_sessions_of_offering(db: Session, course_offering_id: str, first: date | None, last: date) -> int:
    """Open sessions of the offering's non-cancelled classes dated in the range (FR-18: not counted yet)."""
    query = (
        q(db, AttendanceSessionRow)
        .join(
            ScheduledClassRow,
            and_(
                ScheduledClassRow.id == AttendanceSessionRow.scheduled_class_id,
                ScheduledClassRow.organisation_id == AttendanceSessionRow.organisation_id,
            ),
        )
        .where(
            AttendanceSessionRow.status == "open",
            ScheduledClassRow.status != "cancelled",
            ScheduledClassRow.course_offering_id == course_offering_id,
            ScheduledClassRow.class_date <= last,
        )
    )
    if first is not None:
        query = query.where(ScheduledClassRow.class_date >= first)
    return db.scalar(select(func.count()).select_from(query.subquery())) or 0
