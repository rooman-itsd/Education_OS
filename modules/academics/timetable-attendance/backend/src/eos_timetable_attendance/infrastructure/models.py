"""Tables of timetable-attendance. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name (the convention every module with
a backend follows); no foreign key leaves this module. academic_period_id, course_offering_id, section_id,
instructor_assignment_id (academic-management), department_id, instructor_id and opened_by/marked_by/closed_by
(platform/identity users) and student_id (student-information, provisional: PRD Q3) are external ids, stored as plain
strings.

The `*_ref` tables and `section_member` are local read models of other modules' facts (PRD section 8). They are
refreshed only from consumed events, which are not wired yet (PRD section 11, open questions Q1 and Q2); nothing in this
module writes them otherwise."""

from __future__ import annotations

from datetime import UTC, date, datetime, time

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text, Time, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "timetable_attendance_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | date | time | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


class TimetableRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}timetable"
    __table_args__ = (
        Index("ix_timetable_attendance_timetable_period", "organisation_id", "academic_period_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    academic_period_id: Mapped[str] = mapped_column(String(36))
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    version: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TimetableSlotRow(Base, TenantMixin):
    __tablename__ = f"{PREFIX}timetable_slot"
    __table_args__ = (
        Index("ix_timetable_attendance_slot_section", "organisation_id", "section_id"),
        Index("ix_timetable_attendance_slot_assignment", "organisation_id", "instructor_assignment_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    timetable_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}timetable.id"), index=True)
    day_of_week: Mapped[str] = mapped_column(String(10))
    start_time: Mapped[time] = mapped_column(Time)
    end_time: Mapped[time] = mapped_column(Time)
    course_offering_id: Mapped[str] = mapped_column(String(36))
    section_id: Mapped[str] = mapped_column(String(36))
    instructor_assignment_id: Mapped[str] = mapped_column(String(36))
    location_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    effective_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class ScheduledClassRow(Base, TenantMixin, TimestampMixin):
    """One class occurrence. `slot_id` names the slot it was generated from and is None for an ad-hoc class; it is a
    plain id, not a foreign key, because replacing a timetable's slots must not delete or orphan classes that were
    already generated and taught. One class per slot and date (generation is idempotent); an ad-hoc class has no slot,
    and SQL leaves NULLs out of the uniqueness, so any number of them can share a date."""

    __tablename__ = f"{PREFIX}scheduled_class"
    __table_args__ = (
        UniqueConstraint("organisation_id", "slot_id", "class_date", name="uq_timetable_attendance_class_slot_date"),
        Index("ix_timetable_attendance_class_date", "organisation_id", "class_date"),
        Index("ix_timetable_attendance_class_instructor", "organisation_id", "instructor_id", "class_date"),
        Index("ix_timetable_attendance_class_section", "organisation_id", "section_id", "class_date"),
        Index("ix_timetable_attendance_class_offering", "organisation_id", "course_offering_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    timetable_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}timetable.id"), nullable=True, index=True
    )
    slot_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    academic_period_id: Mapped[str] = mapped_column(String(36))
    course_offering_id: Mapped[str] = mapped_column(String(36))
    section_id: Mapped[str] = mapped_column(String(36))
    instructor_assignment_id: Mapped[str] = mapped_column(String(36))
    instructor_id: Mapped[str] = mapped_column(String(36))
    class_date: Mapped[date] = mapped_column(Date)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    location_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class AttendanceSessionRow(Base, TenantMixin, TimestampMixin):
    """At most one per scheduled class."""

    __tablename__ = f"{PREFIX}attendance_session"
    __table_args__ = (
        UniqueConstraint("organisation_id", "scheduled_class_id", name="uq_timetable_attendance_session_class"),
        Index("ix_timetable_attendance_session_status", "organisation_id", "status", "marking_deadline"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    scheduled_class_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}scheduled_class.id"))
    status: Mapped[str] = mapped_column(String(10))
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    opened_by: Mapped[str] = mapped_column(String(36))
    marking_deadline: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_by: Mapped[str | None] = mapped_column(
        String(36), nullable=True
    )  # NULL with closed_at: the system closed it


class AttendanceRecordRow(Base, TenantMixin, TimestampMixin):
    """One student in one session. Opening a session writes one row per eligible student with `status` NULL (not yet
    marked), which is the snapshot of who was eligible (FR-8); marking sets the status, closing turns NULL into
    `absent`. Rows are never deleted (FR-16)."""

    __tablename__ = f"{PREFIX}attendance_record"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "attendance_session_id", "student_id", name="uq_timetable_attendance_record_student"
        ),
        Index("ix_timetable_attendance_record_student", "organisation_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attendance_session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}attendance_session.id"), index=True
    )
    student_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str | None] = mapped_column(String(10), nullable=True)
    remark: Mapped[str | None] = mapped_column(String(500), nullable=True)
    marked_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    marked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AttendanceRecordChangeRow(Base, TenantMixin):
    """The history of a record: every correction keeps the previous value, who changed it, when and why (FR-10)."""

    __tablename__ = f"{PREFIX}record_change"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    attendance_record_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}attendance_record.id"), index=True
    )
    from_status: Mapped[str] = mapped_column(String(10))
    to_status: Mapped[str] = mapped_column(String(10))
    reason: Mapped[str] = mapped_column(Text)
    changed_by: Mapped[str] = mapped_column(String(36))
    changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class OfferingRef(Base, TenantMixin, TimestampMixin):
    """Read model of an academic-management course offering (PRD section 8). Not written until its events are wired."""

    __tablename__ = f"{PREFIX}offering_ref"
    __table_args__ = (
        UniqueConstraint("organisation_id", "course_offering_id", name="uq_timetable_attendance_offering_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_offering_id: Mapped[str] = mapped_column(String(36))
    academic_period_id: Mapped[str] = mapped_column(String(36))
    course_code: Mapped[str] = mapped_column(String(40))
    course_title: Mapped[str] = mapped_column(String(200))
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20))


class SectionRef(Base, TenantMixin, TimestampMixin):
    """Read model of an academic-management section."""

    __tablename__ = f"{PREFIX}section_ref"
    __table_args__ = (UniqueConstraint("organisation_id", "section_id", name="uq_timetable_attendance_section_ref"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    section_id: Mapped[str] = mapped_column(String(36))
    course_offering_id: Mapped[str] = mapped_column(String(36))
    code: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20))


class AssignmentRef(Base, TenantMixin, TimestampMixin):
    """Read model of an academic-management instructor assignment (PRD's `instructor_assignment_ref`, shortened so the
    generated index names stay inside PostgreSQL's 63 characters)."""

    __tablename__ = f"{PREFIX}assignment_ref"
    __table_args__ = (
        UniqueConstraint("organisation_id", "instructor_assignment_id", name="uq_timetable_attendance_assignment_ref"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instructor_assignment_id: Mapped[str] = mapped_column(String(36))
    course_offering_id: Mapped[str] = mapped_column(String(36))
    section_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    instructor_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20))


class SectionMember(Base, TenantMixin, TimestampMixin):
    """Read model of the student-section allocation: who is in a section, from and until when (FR-7)."""

    __tablename__ = f"{PREFIX}section_member"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "section_id", "student_id", "allocated_from", name="uq_timetable_attendance_member"
        ),
        Index("ix_timetable_attendance_member_student", "organisation_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    section_id: Mapped[str] = mapped_column(String(36), index=True)
    student_id: Mapped[str] = mapped_column(String(36))
    student_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    allocated_from: Mapped[date] = mapped_column(Date)
    allocated_to: Mapped[date | None] = mapped_column(Date, nullable=True)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (FR-16). Interim, until the audit SDK ships: the columns
    follow platform/audit's `Record` so each row can be backfilled to `POST /records` with its `client_token`, which
    makes the backfill idempotent. `before` and `after` hold changed fields only, never a whole entity or personal
    details. `reason` is not in the platform contract: it keeps the reason given for a cancellation or correction."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_timetable_attendance_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_timetable_attendance_audit_client_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_token: Mapped[str] = mapped_column(String(120))
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(String(300))
    before: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)  # SQL NULL, not JSON null
    after: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [
    m.__table__
    for m in (
        TimetableRow,
        TimetableSlotRow,
        ScheduledClassRow,
        AttendanceSessionRow,
        AttendanceRecordRow,
        AttendanceRecordChangeRow,
        OfferingRef,
        SectionRef,
        AssignmentRef,
        SectionMember,
        AuditEntry,
    )
]
