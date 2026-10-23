"""Tables of academic-management. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name (the convention every
module with a backend follows); no foreign key leaves this module. department_id, faculty_id (platform/identity
user id) and person_id (student-information Person id) are external ids, stored as plain strings."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "academic_management_"
AMOUNT = Numeric(10, 2, asdecimal=True)  # credits and weekly hours


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


class TermRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}term"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_academic_management_term_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20))


class ProgrammeRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}programme"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_academic_management_programme_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    level: Mapped[str] = mapped_column(String(20))
    department_id: Mapped[str] = mapped_column(String(36))
    duration_terms: Mapped[int] = mapped_column(Integer)
    credits_required: Mapped[Decimal] = mapped_column(AMOUNT)
    published_curriculum_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(20))


class CourseRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}course"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_academic_management_course_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    credits: Mapped[Decimal] = mapped_column(AMOUNT)
    lecture_hours: Mapped[Decimal | None] = mapped_column(AMOUNT, nullable=True)
    practical_hours: Mapped[Decimal | None] = mapped_column(AMOUNT, nullable=True)
    course_type: Mapped[str] = mapped_column(String(20))
    department_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20))


class CurriculumRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}curriculum"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "programme_id", "version", name="uq_academic_management_curriculum_version"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    programme_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}programme.id"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class CurriculumItemRow(Base, TenantMixin):
    __tablename__ = f"{PREFIX}curriculum_item"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    curriculum_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}curriculum.id"), index=True)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course.id"))
    programme_term: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(20))
    credits: Mapped[Decimal] = mapped_column(AMOUNT)


class OfferingRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}offering"
    __table_args__ = (Index("ix_academic_management_offering_period", "organisation_id", "academic_period_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course.id"), index=True)
    academic_period_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}term.id"))
    status: Mapped[str] = mapped_column(String(20))
    programme_ids: Mapped[list] = mapped_column(JSON, default=list)


class SectionRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}section"
    __table_args__ = (
        UniqueConstraint("organisation_id", "course_offering_id", "code", name="uq_academic_management_section_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_offering_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}offering.id"), index=True)
    code: Mapped[str] = mapped_column(String(40))
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))


class FacultyAssignmentRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}faculty_assignment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_offering_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}offering.id"), index=True)
    section_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}section.id"), nullable=True)
    faculty_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(20))
    contact_hours: Mapped[Decimal] = mapped_column(AMOUNT)
    status: Mapped[str] = mapped_column(String(20))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class RosterEntryRow(Base, TenantMixin):
    """Read model built from enrolment-registration's events, one row per registration (FR-14)."""

    __tablename__ = f"{PREFIX}roster_entry"
    __table_args__ = (
        UniqueConstraint("organisation_id", "registration_id", name="uq_academic_management_roster_registration"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    registration_id: Mapped[str] = mapped_column(String(36))
    person_id: Mapped[str] = mapped_column(String(36))
    course_offering_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}offering.id"), index=True)
    section_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}section.id"), index=True)
    student_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    roll_number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20))
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProcessedEventRow(Base, TenantMixin):
    """Envelope ids of consumed events. Delivery is at-least-once and consumers deduplicate on the envelope id
    (platform/event-bus/contracts/events.yaml), so an event already applied is never applied again."""

    __tablename__ = f"{PREFIX}processed_event"
    __table_args__ = (UniqueConstraint("organisation_id", "event_id", name="uq_academic_management_processed_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(120))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [
    m.__table__
    for m in (
        TermRow,
        ProgrammeRow,
        CourseRow,
        CurriculumRow,
        CurriculumItemRow,
        OfferingRow,
        SectionRow,
        FacultyAssignmentRow,
        RosterEntryRow,
        ProcessedEventRow,
    )
]
