"""Tables of alumni. One shared schema with the alumni_ prefix; every table carries organisation_id (TenantMixin) and
gets the tenant_isolation row-level-security policy on Postgres. Nothing is deleted: alumni are archived, assignments
ended and sessions cancelled (PRD). Students and staff are platform/identity user ids, never foreign keys."""

from __future__ import annotations

from datetime import date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "alumni_"
ACTIVE_ONLY = text("status = 'active'")


class Alumnus(Base, TenantMixin, TimestampMixin):
    """A directory record kept by staff. Verified by its creator on creation (A2). Contact details and notes are for
    staff; the contact details reach a student only as the mentor of their own active assignment (A5)."""

    __tablename__ = f"{PREFIX}alumnus"
    __table_args__ = (Index("ix_alumni_alumnus_listing", "organisation_id", "status", "created_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    full_name: Mapped[str] = mapped_column(String(200))
    graduation_year: Mapped[int] = mapped_column(Integer)
    programme: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    current_designation: Mapped[str | None] = mapped_column(String(200), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(200), nullable=True)
    city: Mapped[str | None] = mapped_column(String(200), nullable=True)
    email: Mapped[str | None] = mapped_column(String(200), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(200), nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(String(200), nullable=True)
    is_mentor: Mapped[bool] = mapped_column(Boolean, default=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="active")
    created_by: Mapped[str] = mapped_column(String(36))
    verified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Assignment(Base, TenantMixin, TimestampMixin):
    """A mentor assigned to a student. One active assignment per (organisation, student), kept by a partial unique
    index; a student is always looked up by (organisation_id, student_id), never by student_id alone (PRD)."""

    __tablename__ = f"{PREFIX}mentoring_assignment"
    __table_args__ = (
        Index(
            "uq_alumni_assignment_active_student",
            "organisation_id",
            "student_id",
            unique=True,
            postgresql_where=ACTIVE_ONLY,
            sqlite_where=ACTIVE_ONLY,
        ),
        Index("ix_alumni_assignment_student", "organisation_id", "student_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    mentor_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}alumnus.id"), index=True)
    student_id: Mapped[str] = mapped_column(String(36))
    student_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    started_on: Mapped[date] = mapped_column(Date)
    ended_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)
    focus: Mapped[str | None] = mapped_column(String(200), nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(36))
    end_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class MentoringSession(Base, TenantMixin, TimestampMixin):
    """An optional record of a mentoring session. `notes` are for staff only and never reach a student or an event."""

    __tablename__ = f"{PREFIX}mentoring_session"
    __table_args__ = (Index("ix_alumni_session_assignment_time", "assignment_id", "scheduled_at"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}mentoring_assignment.id"))
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mode: Mapped[str] = mapped_column(String(10))
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    topic: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="scheduled")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only, never names, contact details or notes. Stands in for the audit SDK until it
    ships, as in e-office and hr-payroll."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_alumni_audit_entity", "organisation_id", "entity", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [m.__table__ for m in (Alumnus, Assignment, MentoringSession, AuditEntry)]
