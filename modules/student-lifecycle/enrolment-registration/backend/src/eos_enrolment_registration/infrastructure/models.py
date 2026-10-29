"""SQLAlchemy models for enrolment-registration. Every table is prefixed enrolment_registration_ and carries
organisation_id; the migration puts the tenant_isolation row-level-security policy on each. to_dict() returns the
contract's field names."""

from __future__ import annotations

from datetime import UTC, date, datetime

import sqlalchemy as sa
from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..domain import enums as e

PREFIX = "enrolment_registration_"

ACTIVE_ENROLMENT = sa.text("status = 'active'")
CONFIRMED_REGISTRATION = sa.text("status = 'confirmed'")


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; every stored datetime is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


class ProgrammeEnrolment(Base, TenantMixin):
    __tablename__ = f"{PREFIX}programme_enrolment"
    __table_args__ = (
        Index(f"ix_{PREFIX}programme_enrolment_organisation_id", "organisation_id"),
        Index(f"uq_{PREFIX}programme_enrolment_roll_number", "organisation_id", "roll_number", unique=True),
        Index(
            f"uq_{PREFIX}programme_enrolment_active",
            "organisation_id",
            "person_id",
            "programme_id",
            unique=True,
            sqlite_where=ACTIVE_ENROLMENT,
            postgresql_where=ACTIVE_ENROLMENT,
        ),
        Index(f"ix_{PREFIX}programme_enrolment_programme", "organisation_id", "programme_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    person_id: Mapped[str] = mapped_column(String(36), nullable=False)
    student_name: Mapped[str] = mapped_column(String(200), nullable=False)
    programme_id: Mapped[str] = mapped_column(String(36), nullable=False)
    roll_number: Mapped[str] = mapped_column(String(32), nullable=False)
    start_academic_period_id: Mapped[str] = mapped_column(String(36), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=e.ACTIVE)
    source_application_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    enrolled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    enrolled_by: Mapped[str] = mapped_column(String(36), nullable=False)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "person_id": self.person_id,
            "student_name": self.student_name,
            "programme_id": self.programme_id,
            "roll_number": self.roll_number,
            "start_academic_period_id": self.start_academic_period_id,
            "status": self.status,
            "source_application_id": self.source_application_id,
            "enrolled_at": iso(self.enrolled_at),
            "ended_at": iso(self.ended_at),
            "end_reason": self.end_reason,
        }


class RollNumberCounter(Base, TenantMixin):
    """The last roll number issued per organisation and year; numbers are never reused (PRD §6 rule 7)."""

    __tablename__ = f"{PREFIX}roll_number_counter"
    __table_args__ = (Index(f"ix_{PREFIX}roll_number_counter_organisation_id", "organisation_id"),)

    organisation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    year: Mapped[int] = mapped_column(Integer, primary_key=True)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RegistrationWindow(Base, TenantMixin):
    __tablename__ = f"{PREFIX}registration_window"
    __table_args__ = (
        Index(f"ix_{PREFIX}registration_window_organisation_id", "organisation_id"),
        Index(f"uq_{PREFIX}registration_window_term", "organisation_id", "academic_period_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    academic_period_id: Mapped[str] = mapped_column(String(36), nullable=False)
    opens_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(36), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        """Contract RegistrationWindow without is_open, which depends on the time of the request."""
        return {
            "academic_period_id": self.academic_period_id,
            "opens_at": iso(self.opens_at),
            "closes_at": iso(self.closes_at),
            "updated_at": iso(self.updated_at),
        }


class CourseRegistration(Base, TenantMixin):
    __tablename__ = f"{PREFIX}course_registration"
    __table_args__ = (
        Index(f"ix_{PREFIX}course_registration_organisation_id", "organisation_id"),
        Index(
            f"uq_{PREFIX}course_registration_confirmed",
            "organisation_id",
            "person_id",
            "course_offering_id",
            unique=True,
            sqlite_where=CONFIRMED_REGISTRATION,
            postgresql_where=CONFIRMED_REGISTRATION,
        ),
        Index(f"ix_{PREFIX}course_registration_enrolment", "programme_enrolment_id"),
        Index(f"ix_{PREFIX}course_registration_section", "organisation_id", "section_id", "status"),
        Index(
            f"ix_{PREFIX}course_registration_term",
            "organisation_id",
            "academic_period_id",
            "course_offering_id",
            "status",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    programme_enrolment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}programme_enrolment.id"), nullable=False
    )
    person_id: Mapped[str] = mapped_column(String(36), nullable=False)
    course_offering_id: Mapped[str] = mapped_column(String(36), nullable=False)
    section_id: Mapped[str] = mapped_column(String(36), nullable=False)
    academic_period_id: Mapped[str] = mapped_column(String(36), nullable=False)
    registration_type: Mapped[str] = mapped_column(String(20), nullable=False, default=e.REGULAR)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=e.CONFIRMED)
    references_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    section_since: Mapped[date] = mapped_column(Date, nullable=False)
    confirmed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    confirmed_by: Mapped[str] = mapped_column(String(36), nullable=False)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    withdrawal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    def to_dict(self) -> dict:
        """Contract CourseRegistration without student_name and roll_number, which come from the enrolment."""
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "programme_enrolment_id": self.programme_enrolment_id,
            "person_id": self.person_id,
            "course_offering_id": self.course_offering_id,
            "section_id": self.section_id,
            "academic_period_id": self.academic_period_id,
            "registration_type": self.registration_type,
            "status": self.status,
            "references_verified": self.references_verified,
            "section_since": iso(self.section_since),
            "confirmed_at": iso(self.confirmed_at),
            "withdrawn_at": iso(self.withdrawn_at),
            "withdrawal_reason": self.withdrawal_reason,
        }


# ---------------------------------------------------------------- local copies of academic-management


class TermRef(Base, TenantMixin):
    __tablename__ = f"{PREFIX}term_ref"
    __table_args__ = (Index(f"ix_{PREFIX}term_ref_organisation_id", "organisation_id"),)

    academic_period_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    starts_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class OfferingRef(Base, TenantMixin):
    __tablename__ = f"{PREFIX}offering_ref"
    __table_args__ = (
        Index(f"ix_{PREFIX}offering_ref_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}offering_ref_term", "organisation_id", "academic_period_id"),
    )

    course_offering_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    academic_period_id: Mapped[str] = mapped_column(String(36), nullable=False)
    course_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    course_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="planned")


class SectionRef(Base, TenantMixin):
    __tablename__ = f"{PREFIX}section_ref"
    __table_args__ = (
        Index(f"ix_{PREFIX}section_ref_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}section_ref_offering", "organisation_id", "course_offering_id"),
    )

    section_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    course_offering_id: Mapped[str] = mapped_column(String(36), nullable=False)
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=e.OPEN)


class ProcessedEvent(Base, TenantMixin):
    """Envelope ids of consumed events: delivery is at-least-once, so an event already applied is skipped."""

    __tablename__ = f"{PREFIX}processed_event"
    __table_args__ = (
        Index(f"ix_{PREFIX}processed_event_organisation_id", "organisation_id"),
        Index(f"uq_{PREFIX}processed_event_event", "organisation_id", "event_id", unique=True),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    event_id: Mapped[str] = mapped_column(String(36), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


class AuditEntry(Base, TenantMixin):
    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index(f"ix_{PREFIX}audit_entry_organisation_id", "organisation_id"),
        Index(f"ix_{PREFIX}audit_entry_entity", "entity", "entity_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str] = mapped_column(String(36), nullable=False)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str] = mapped_column(String(36), nullable=False)
    detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)


MODELS = (
    ProgrammeEnrolment,
    RollNumberCounter,
    RegistrationWindow,
    CourseRegistration,
    TermRef,
    OfferingRef,
    SectionRef,
    ProcessedEvent,
    AuditEntry,
)
TABLES = [m.__table__ for m in MODELS]
