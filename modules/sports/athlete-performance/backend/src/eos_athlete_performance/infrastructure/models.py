"""Tables of athlete-performance. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module (user, coach and student ids are plain values)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "athlete_performance_"


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


class Discipline(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}discipline"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_athlete_performance_discipline_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Metric(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}metric"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_athlete_performance_metric_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    unit: Mapped[str] = mapped_column(String(30))
    direction: Mapped[str] = mapped_column(String(20))
    discipline_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}discipline.id"), nullable=True, index=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Athlete(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}athlete"
    __table_args__ = (UniqueConstraint("organisation_id", "user_id", name="uq_athlete_performance_athlete_user"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    student_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    full_name: Mapped[str] = mapped_column(String(200))
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    gender: Mapped[str | None] = mapped_column(String(20), nullable=True)
    primary_discipline_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}discipline.id"), index=True)
    discipline_ids: Mapped[list] = mapped_column(JSON, default=list)
    coach_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    squad: Mapped[str | None] = mapped_column(String(120), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)


class Result(Base, TenantMixin, TimestampMixin, _Updated):
    """One measured value. Kept as history: corrections are updates, never deletes."""

    __tablename__ = f"{PREFIX}result"
    __table_args__ = (Index("ix_athlete_performance_result_athlete_metric", "athlete_id", "metric_id", "recorded_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}athlete.id"))
    metric_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}metric.id"), index=True)
    value: Mapped[float] = mapped_column(Float)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    context: Mapped[str] = mapped_column(String(20))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))


class FitnessTest(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}fitness_test"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_athlete_performance_fitness_test_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    metric_ids: Mapped[list] = mapped_column(JSON, default=list)
    discipline_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}discipline.id"), nullable=True)


class Assessment(Base, TenantMixin, TimestampMixin, _Updated):
    """One fitness test for one athlete on one day; measurements are [{metric_id, value}]."""

    __tablename__ = f"{PREFIX}assessment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}athlete.id"), index=True)
    fitness_test_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}fitness_test.id"), index=True)
    assessed_on: Mapped[date] = mapped_column(Date)
    measurements: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    assessor_id: Mapped[str] = mapped_column(String(36))


class Benchmark(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}benchmark"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    metric_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}metric.id"), index=True)
    discipline_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}discipline.id"), nullable=True)
    level: Mapped[str] = mapped_column(String(60))
    gender: Mapped[str | None] = mapped_column(String(10), nullable=True)
    age_group: Mapped[str | None] = mapped_column(String(30), nullable=True)
    target_value: Mapped[float] = mapped_column(Float)
    source: Mapped[str | None] = mapped_column(String(300), nullable=True)


class Clearance(Base, TenantMixin, _Updated):
    """An athlete's current fitness clearance: status only, never clinical detail."""

    __tablename__ = f"{PREFIX}clearance"
    __table_args__ = (
        UniqueConstraint("organisation_id", "athlete_id", name="uq_athlete_performance_clearance_athlete"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}athlete.id"))
    status: Mapped[str] = mapped_column(String(20))
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    restrictions: Mapped[str | None] = mapped_column(Text, nullable=True)
    set_by: Mapped[str] = mapped_column(String(36))
    set_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when. Interim, until the audit SDK ships: the columns follow platform/audit's `Record`,
    as academic-management's, hostel's and helpdesk's audit tables do, so each row can be backfilled with its
    `client_token`. `before` and `after` hold changed fields only, never names, notes or clearance restrictions."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_athlete_performance_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_athlete_performance_audit_client_token"),
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


TABLES = [
    m.__table__
    for m in (Discipline, Metric, Athlete, Result, FitnessTest, Assessment, Benchmark, Clearance, AuditEntry)
]
