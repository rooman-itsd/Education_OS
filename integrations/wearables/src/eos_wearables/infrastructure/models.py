"""Own schema, every table prefixed wearables_ and carrying organisation_id with forced row-level security
(db/migrations). The Alembic chain keeps its own version table."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "wearables_"


def aware(value: datetime | None) -> datetime | None:
    """SQLite hands datetimes back without a zone; everything here is UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def iso(value: datetime | date | None) -> str | None:
    if isinstance(value, datetime):
        value = aware(value)
    return value.isoformat() if value else None


class LinkState(Base, TenantMixin):
    """One athlete's link to one provider, as far as this adapter needs to know it. The tokens are the hub's."""

    __tablename__ = f"{PREFIX}link_state"
    __table_args__ = (
        UniqueConstraint("organisation_id", "account_link_id", name="uq_wearables_link"),
        Index("ix_wearables_link_subject", "provider", "provider_subject"),
        Index("ix_wearables_link_person", "organisation_id", "person_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(String(36))
    account_link_id: Mapped[str] = mapped_column(String(36))
    person_id: Mapped[str] = mapped_column(String(36))
    provider: Mapped[str] = mapped_column(String(20))
    provider_subject: Mapped[str | None] = mapped_column(String(128), nullable=True)  # the athlete's id at the provider
    status: Mapped[str] = mapped_column(String(10), default="pending")  # pending | active | expired | revoked | error
    status_since: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    data_types: Mapped[list] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_data_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0)
    failing_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error_code: Mapped[str | None] = mapped_column(String(30), nullable=True)


class Record(Base, TenantMixin):
    """One normalised record (the port's `records` shapes, fixed units) from one link. Upserted on
    (account_link_id, data_type, provider_record_id), so a redelivery or a correction changes one row."""

    __tablename__ = f"{PREFIX}record"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "account_link_id", "data_type", "provider_record_id", name="uq_wearables_record"
        ),
        Index("ix_wearables_record_read", "organisation_id", "person_id", "data_type", "record_date"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    account_link_id: Mapped[str] = mapped_column(String(36), index=True)
    person_id: Mapped[str] = mapped_column(String(36))
    provider: Mapped[str] = mapped_column(String(20))
    data_type: Mapped[str] = mapped_column(String(30))
    provider_record_id: Mapped[str] = mapped_column(String(200))
    record_date: Mapped[date] = mapped_column(Date)  # the day it belongs to (UTC day of the start for an activity)
    fields: Mapped[dict] = mapped_column(JSON)  # the port's normalised shape for the data type
    display_scope: Mapped[str] = mapped_column(String(12), default="all")  # all | athlete_only
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ReadLog(Base, TenantMixin):
    """Every read, with its stated purpose (docs/prd.md, "Reading data"). No readings are kept here."""

    __tablename__ = f"{PREFIX}read_log"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    caller_module: Mapped[str | None] = mapped_column(String(60), nullable=True)
    purpose: Mapped[str] = mapped_column(String(40))
    data_type: Mapped[str] = mapped_column(String(30))
    date_from: Mapped[date] = mapped_column(Date)
    date_to: Mapped[date] = mapped_column(Date)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change. Ids and the action only, never a reading. Stands in for the
    audit SDK until it ships, as in alumni and the other modules."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_wearables_audit_entity", "organisation_id", "entity", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)  # the hub's delivery id, when there is one
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [m.__table__ for m in (LinkState, Record, ReadLog, AuditEntry)]
