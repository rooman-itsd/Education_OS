"""Tables of productions. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves
this module (resource_id is a plain reference to a facility-booking resource, user ids to identity)."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "productions_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


class Production(Base, TenantMixin, TimestampMixin):
    """One performance, exhibition, screening, hackathon, moot or conference."""

    __tablename__ = f"{PREFIX}production"
    __table_args__ = (
        # Idempotency per caller, not per organisation: one person's retry must never hand them somebody
        # else's production (the lesson of #317's audit, which found a shared client_token did exactly that).
        UniqueConstraint("organisation_id", "created_by", "client_token", name="uq_productions_client_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), index=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    department: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(200), nullable=True)
    resource_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    starts_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    call_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lead_user_id: Mapped[str] = mapped_column(String(36), index=True)
    created_by: Mapped[str] = mapped_column(String(36))
    client_token: Mapped[str | None] = mapped_column(String(100), nullable=True)
    cancelled_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ProductionRole(Base, TenantMixin, TimestampMixin):
    """A part or crew job offered to one person on one production."""

    __tablename__ = f"{PREFIX}role"
    __table_args__ = (
        UniqueConstraint("organisation_id", "production_id", "user_id", "role_name", name="uq_productions_role"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    production_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}production.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    role_name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="cast")
    status: Mapped[str] = mapped_column(String(20), index=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    assigned_by: Mapped[str] = mapped_column(String(36))
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ProductionTask(Base, TenantMixin, TimestampMixin):
    """One thing that has to be done before a production can go ahead."""

    __tablename__ = f"{PREFIX}task"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    production_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}production.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(20), default="open", index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # keeps the order the tasks were added in
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    assignee_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    added_by: Mapped[str] = mapped_column(String(36))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


TABLES = [m.__table__ for m in (Production, ProductionRole, ProductionTask)]
