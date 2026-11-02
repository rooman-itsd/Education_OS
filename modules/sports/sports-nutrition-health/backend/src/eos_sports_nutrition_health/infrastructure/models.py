"""Tables of sports-nutrition-health. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module: athlete ids are athlete-performance's, practitioner and user ids are platform/identity's, all plain values."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "sports_nutrition_health_"


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


class _Updated:
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Plan(Base, TenantMixin, TimestampMixin, _Updated):
    """A nutrition (diet) plan for one athlete over a period."""

    __tablename__ = f"{PREFIX}plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    goal: Mapped[str] = mapped_column(String(20))
    daily_calories: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protein_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    carbohydrate_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    fat_g: Mapped[float | None] = mapped_column(Float, nullable=True)
    meals: Mapped[list] = mapped_column(JSON, default=list)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    review_due_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    nutritionist_id: Mapped[str] = mapped_column(String(36))


class PlanReview(Base, TenantMixin, TimestampMixin, _Updated):
    """A review of a plan. Reviews are a record: they are added, never changed."""

    __tablename__ = f"{PREFIX}plan_review"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}plan.id"), index=True)
    reviewed_on: Mapped[date] = mapped_column(Date)
    outcome: Mapped[str] = mapped_column(String(10))
    body_weight_kg: Mapped[float | None] = mapped_column(Float, nullable=True)
    next_review_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str] = mapped_column(String(36))


class HealthRecord(Base, TenantMixin, TimestampMixin, _Updated):
    """Confidential: readable only with health-record:read, never in events or audit values."""

    __tablename__ = f"{PREFIX}health_record"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36), index=True)
    record_type: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    details: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_on: Mapped[date] = mapped_column(Date)
    recorded_by: Mapped[str] = mapped_column(String(36))


class Injury(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}injury"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36), index=True)
    body_part: Mapped[str] = mapped_column(String(120))
    injury_type: Mapped[str | None] = mapped_column(String(120), nullable=True)
    severity: Mapped[str] = mapped_column(String(10))
    occurred_on: Mapped[date] = mapped_column(Date)
    context: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    expected_return_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    resolved_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    clinical_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reported_by: Mapped[str] = mapped_column(String(36))


class Appointment(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}appointment"
    __table_args__ = (Index("ix_sports_nutrition_health_appointment_time", "organisation_id", "scheduled_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36), index=True)
    practitioner_id: Mapped[str] = mapped_column(String(36), index=True)
    appointment_type: Mapped[str] = mapped_column(String(20))
    injury_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}injury.id"), nullable=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AthleteLink(Base, TenantMixin):
    """Which platform/identity user is which athlete, learnt from athlete-performance.athlete.registered. It lets an
    athlete see only their own rows without this module importing athlete-performance."""

    __tablename__ = f"{PREFIX}athlete_link"
    __table_args__ = (
        UniqueConstraint("organisation_id", "athlete_id", name="uq_sports_nutrition_health_link_athlete"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when. Interim, until the audit SDK ships: the columns follow platform/audit's `Record`,
    as academic-management's audit table does. `before` and `after` hold changed fields only, never clinical or
    free-text fields (service.NOT_RECORDED)."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_sports_nutrition_health_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_sports_nutrition_health_audit_client_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_token: Mapped[str] = mapped_column(String(120))
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(String(300))
    before: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [m.__table__ for m in (Plan, PlanReview, HealthRecord, Injury, Appointment, AthleteLink, AuditEntry)]
