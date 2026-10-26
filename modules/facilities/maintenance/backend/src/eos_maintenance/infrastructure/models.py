"""Tables of maintenance. Every table carries organisation_id (TenantMixin), so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this module (a ticket's
target id is a plain reference to asset-management, facility-booking or inventory-equipment)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "maintenance_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


class Category(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}category"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_maintenance_category_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_priority: Mapped[str] = mapped_column(String(10), default="medium")
    default_assignee_ids: Mapped[list] = mapped_column(JSON, default=list)
    sla_override: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Ticket(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}ticket"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_maintenance_ticket_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20))
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}category.id"), index=True)
    target_kind: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_label: Mapped[str] = mapped_column(String(300))
    priority: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), index=True)
    blocks_use: Mapped[bool] = mapped_column(Boolean, default=False)
    reported_by: Mapped[str] = mapped_column(String(36), index=True)
    assignee_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    vendor: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    hold_reason: Mapped[str | None] = mapped_column(String(20), nullable=True)
    held_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    held_minutes: Mapped[int] = mapped_column(Integer, default=0)
    schedule_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    source: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    photo_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    response_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    resolution_due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    response_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    resolution_breached: Mapped[bool] = mapped_column(Boolean, default=False)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class WorkEntry(Base, TenantMixin, TimestampMixin):
    """Append-only work log line: a note, time spent, a part used or a cost. Never updated or deleted."""

    __tablename__ = f"{PREFIX}work_entry"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}ticket.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # keeps the order entries were added in
    kind: Mapped[str] = mapped_column(String(10))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    item_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    quantity: Mapped[float | None] = mapped_column(Numeric(12, 3, asdecimal=False), nullable=True)
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))


class Schedule(Base, TenantMixin, TimestampMixin):
    """Preventive plan for one target. Raises a ticket lead_days before each due date."""

    __tablename__ = f"{PREFIX}schedule"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}category.id"), index=True)
    target_kind: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    target_label: Mapped[str] = mapped_column(String(300))
    kind: Mapped[str] = mapped_column(String(20), default="preventive")
    every: Mapped[int] = mapped_column(Integer)
    unit: Mapped[str] = mapped_column(String(10))
    next_due_on: Mapped[date] = mapped_column(Date)
    lead_days: Mapped[int] = mapped_column(Integer)
    priority: Mapped[str | None] = mapped_column(String(10), nullable=True)
    default_assignee_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    checklist: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    open_ticket_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    last_completed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


TABLES = [m.__table__ for m in (Category, Ticket, WorkEntry, Schedule)]
