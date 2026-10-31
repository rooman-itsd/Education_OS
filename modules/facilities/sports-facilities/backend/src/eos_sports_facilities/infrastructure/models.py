"""Tables of sports-facilities. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module (user ids and facility-booking references are plain values)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "sports_facilities_"


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


class Facility(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}facility"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_sports_facilities_facility_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    facility_type: Mapped[str] = mapped_column(String(20), index=True)
    sports: Mapped[list] = mapped_column(JSON, default=list)
    surface: Mapped[str | None] = mapped_column(String(120), nullable=True)
    indoor: Mapped[bool] = mapped_column(Boolean)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="operational", index=True)
    status_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Space(Base, TenantMixin, TimestampMixin, _Updated):
    """A part of a facility used on its own, e.g. Court 2 or Lanes 1-4."""

    __tablename__ = f"{PREFIX}space"
    __table_args__ = (
        UniqueConstraint("organisation_id", "facility_id", "name", name="uq_sports_facilities_space_name"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}facility.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sports: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class OperatingHoursSlot(Base, TenantMixin):
    """One opening slot of the weekly hours, in the institution's local time. No rows means always open."""

    __tablename__ = f"{PREFIX}operating_hours"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}facility.id"), index=True)
    day_of_week: Mapped[int] = mapped_column(Integer)
    opens_at: Mapped[str] = mapped_column(String(5))
    closes_at: Mapped[str] = mapped_column(String(5))


class UsageRecord(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}usage"
    __table_args__ = (Index("ix_sports_facilities_usage_facility_from", "organisation_id", "facility_id", "used_from"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    facility_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}facility.id"))
    space_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}space.id"), nullable=True)
    used_from: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used_to: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    purpose: Mapped[str] = mapped_column(String(30), index=True)
    group_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    headcount: Mapped[int | None] = mapped_column(Integer, nullable=True)
    booking_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when. Interim, until the audit SDK ships: the columns follow platform/audit's `Record`,
    as athlete-performance's, academic-management's, hostel's and helpdesk's audit tables do, so each row can be
    backfilled with its `client_token`. `before` and `after` hold the changed fields only, never free text."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_sports_facilities_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_sports_facilities_audit_client_token"),
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


TABLES = [m.__table__ for m in (Facility, Space, OperatingHoursSlot, UsageRecord, AuditEntry)]
