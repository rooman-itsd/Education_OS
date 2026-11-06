"""Tables of field-training. Every table carries organisation_id (TenantMixin), so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this module.
trainee_id, supervisor_id and the supervisors' person_ids refer to identity / student-information / hr-payroll by id
only. Hours are stored as whole minutes (domain/rules.py) so sums are exact."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "field_training_"


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


class Site(Base, TenantMixin, TimestampMixin):
    """A host site. `kind` is the organisation's own label (ward, partner school, plant, ...)."""

    __tablename__ = f"{PREFIX}site"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str | None] = mapped_column(String(100), nullable=True)
    address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class SiteSupervisor(Base, TenantMixin):
    """A supervisor attached to a site, in the order the coordinator listed them. Replaced when the list changes."""

    __tablename__ = f"{PREFIX}site_supervisor"
    __table_args__ = (
        UniqueConstraint("organisation_id", "site_id", "person_id", name="uq_field_training_site_supervisor"),
        Index("ix_field_training_site_supervisor_person", "organisation_id", "person_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}site.id"), index=True)
    person_id: Mapped[str] = mapped_column(String(36))
    position: Mapped[int] = mapped_column(Integer)


class Opening(Base, TenantMixin, TimestampMixin):
    """An opening at a site. Seats filled are counted from its placements, never stored, so they cannot drift."""

    __tablename__ = f"{PREFIX}opening"
    __table_args__ = (Index("ix_field_training_opening_status_start", "organisation_id", "status", "starts_on"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    site_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}site.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    discipline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    seats: Mapped[int] = mapped_column(Integer)
    required_minutes: Mapped[int] = mapped_column(Integer, default=0)
    allow_applications: Mapped[bool] = mapped_column(Boolean, default=False)
    eligibility: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10))
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OpeningSupervisor(Base, TenantMixin):
    """A supervisor named on an opening, in order; the first is the default supervisor of its placements."""

    __tablename__ = f"{PREFIX}opening_supervisor"
    __table_args__ = (
        UniqueConstraint("organisation_id", "opening_id", "person_id", name="uq_field_training_opening_supervisor"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    opening_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}opening.id"), index=True)
    person_id: Mapped[str] = mapped_column(String(36))
    position: Mapped[int] = mapped_column(Integer)


class Placement(Base, TenantMixin, TimestampMixin):
    """A trainee's placement in an opening: an application (requested) or a placement (assigned onwards).
    Names are cached from student-information and hr-payroll events once the module consumes them; null until then."""

    __tablename__ = f"{PREFIX}placement"
    __table_args__ = (
        Index("ix_field_training_placement_trainee", "organisation_id", "trainee_id", "status"),
        Index("ix_field_training_placement_supervisor", "organisation_id", "supervisor_id", "status"),
        Index("ix_field_training_placement_opening", "organisation_id", "opening_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    opening_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}opening.id"))
    site_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}site.id"))
    trainee_id: Mapped[str] = mapped_column(String(36))
    trainee_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supervisor_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    supervisor_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    required_minutes: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(10))
    statement: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    hours_overridden: Mapped[bool] = mapped_column(Boolean, default=False)
    started_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LogEntry(Base, TenantMixin, TimestampMixin):
    """One logbook entry. Verified entries are locked; their minutes count toward the requirement."""

    __tablename__ = f"{PREFIX}log_entry"
    __table_args__ = (
        Index("ix_field_training_log_placement_date", "organisation_id", "placement_id", "date"),
        Index("ix_field_training_log_placement_status", "organisation_id", "placement_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    placement_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}placement.id"))
    date: Mapped[date] = mapped_column(Date)
    minutes: Mapped[int] = mapped_column(Integer)
    activities: Mapped[str] = mapped_column(Text)
    reflection: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Assessment(Base, TenantMixin):
    """A mid or final assessment outcome on the organisation's own scale. Rubrics belong to skill-progress."""

    __tablename__ = f"{PREFIX}assessment"
    __table_args__ = (Index("ix_field_training_assessment_placement", "organisation_id", "placement_id", "stage"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    placement_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}placement.id"))
    assessor_id: Mapped[str] = mapped_column(String(36))
    stage: Mapped[str] = mapped_column(String(10))
    outcome: Mapped[str] = mapped_column(String(200))
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only, never personal details or log text. Stands in for the audit SDK until it ships."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_field_training_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Site, SiteSupervisor, Opening, OpeningSupervisor, Placement, LogEntry, Assessment, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
