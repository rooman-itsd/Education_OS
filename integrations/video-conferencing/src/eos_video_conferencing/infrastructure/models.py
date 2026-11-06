"""Own schema, every table prefixed video_conferencing_ and carrying organisation_id with forced row-level security
(db/migrations). The Alembic chain keeps its own version table."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, BigInteger, Boolean, Date, DateTime, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "video_conferencing_"


def aware(value: datetime | None) -> datetime | None:
    """SQLite hands datetimes back without a zone; everything here is UTC."""
    if value is None or value.tzinfo is not None:
        return value
    return value.replace(tzinfo=UTC)


def iso(value: datetime | None) -> str | None:
    value = aware(value)
    return value.isoformat() if value else None


class Meeting(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}meeting"
    __table_args__ = (
        UniqueConstraint("organisation_id", "meeting_key", name="uq_video_conferencing_meeting_key"),
        Index("ix_video_conferencing_meeting_provider_ref", "provider", "provider_meeting_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(String(36), index=True)
    meeting_key: Mapped[str] = mapped_column(String(128))
    caller_module: Mapped[str | None] = mapped_column(String(60), nullable=True)
    provider: Mapped[str] = mapped_column(String(20))
    provider_meeting_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    provider_instance_id: Mapped[str | None] = mapped_column(String(256), nullable=True)  # Zoom uuid, Webex instance id
    host_user_id: Mapped[str | None] = mapped_column(String(256), nullable=True)  # who owns it at the provider
    room_name: Mapped[str | None] = mapped_column(String(120), nullable=True)  # Jitsi
    # creating (reserved while the provider call runs) | scheduled | started | ended | cancelled
    status: Mapped[str] = mapped_column(String(12), default="creating")
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    join_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted
    host_join_url: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted
    passcode: Mapped[str | None] = mapped_column(Text, nullable=True)  # encrypted
    attendance_fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Attendance(Base, TenantMixin):
    __tablename__ = f"{PREFIX}attendance"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    meeting_id: Mapped[str] = mapped_column(String(36), index=True)
    person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)  # only when unmatched
    role: Mapped[str] = mapped_column(String(10))
    total_seconds: Mapped[int] = mapped_column(Integer)
    intervals: Mapped[list] = mapped_column(JSON, default=list)
    complete: Mapped[bool] = mapped_column(Boolean, default=False)


class Recording(Base, TenantMixin):
    __tablename__ = f"{PREFIX}recording"
    __table_args__ = (UniqueConstraint("meeting_id", "provider_recording_id", name="uq_video_conferencing_recording"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    meeting_id: Mapped[str] = mapped_column(String(36), index=True)
    provider_recording_id: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(12))
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    bytes: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)  # of the imported copy


class GraphSubscription(Base, TenantMixin):
    __tablename__ = f"{PREFIX}graph_subscription"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(String(36), index=True)
    subscription_id: Mapped[str] = mapped_column(String(128), index=True)
    resource: Mapped[str] = mapped_column(String(300))
    client_state_ref: Mapped[str] = mapped_column(
        String(64)
    )  # a nonce; the clientState itself is derived, never stored
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class HostQuota(Base, TenantMixin):
    """Create and update calls made for one provider user on one UTC day (Zoom allows 100 per user per day)."""

    __tablename__ = f"{PREFIX}host_quota"
    __table_args__ = (
        UniqueConstraint("organisation_id", "connection_id", "host_user_id", "day", name="uq_video_conferencing_quota"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    connection_id: Mapped[str] = mapped_column(String(36))
    host_user_id: Mapped[str] = mapped_column(String(256))
    day: Mapped[date] = mapped_column(Date)
    calls: Mapped[int] = mapped_column(Integer, default=0)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change. Holds ids and the action only, never names, links or
    passcodes. Stands in for the audit SDK until it ships, as in alumni and the other modules."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_video_conferencing_audit_entity", "organisation_id", "entity", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)  # the hub's delivery id, when there is one
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [m.__table__ for m in (Meeting, Attendance, Recording, GraphSubscription, HostQuota, AuditEntry)]
