"""Tables of facility-booking. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key
leaves this module."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "facility_booking_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


class ResourceType(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}resource_type"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_facility_booking_resource_type_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    colour: Mapped[str | None] = mapped_column(String(7), nullable=True)
    default_rules: Mapped[dict] = mapped_column(JSON, default=dict)


class Resource(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}resource"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_facility_booking_resource_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    type_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}resource_type.id"), index=True)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    capacity: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    image_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    approver_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    rules: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="active")
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class OpeningHoursRow(Base, TenantMixin):
    __tablename__ = f"{PREFIX}opening_hours"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}resource.id"), index=True)
    weekday: Mapped[int] = mapped_column(Integer)
    opens: Mapped[str] = mapped_column(String(5))
    closes: Mapped[str] = mapped_column(String(5))


class Blackout(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}blackout"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}resource.id"), index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    reason: Mapped[str] = mapped_column(String(300))
    created_by: Mapped[str] = mapped_column(String(36))


class BookingSeries(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}series"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}resource.id"), index=True)
    recurrence: Mapped[dict] = mapped_column(JSON, default=dict)
    booked_by: Mapped[str] = mapped_column(String(36))
    booked_for: Mapped[str] = mapped_column(String(36))


class Booking(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}booking"
    __table_args__ = (
        Index("ix_facility_booking_booking_resource_start", "organisation_id", "resource_id", "start_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    resource_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}resource.id"))
    series_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}series.id"), nullable=True)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    end_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    party_size: Mapped[int] = mapped_column(Integer, default=1)
    booked_by: Mapped[str] = mapped_column(String(36), index=True)
    booked_for: Mapped[str] = mapped_column(String(36), index=True)
    source: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


TABLES = [m.__table__ for m in (ResourceType, Resource, OpeningHoursRow, Blackout, BookingSeries, Booking)]
