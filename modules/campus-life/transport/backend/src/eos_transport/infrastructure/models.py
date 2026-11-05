"""Tables of transport. Every table carries organisation_id (TenantMixin), so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this module.
person_id and user ids refer to identity / student-information / hr-payroll by id only."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "transport_"


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


class Stop(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}stop"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Vehicle(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}vehicle"
    __table_args__ = (UniqueConstraint("organisation_id", "registration_no", name="uq_transport_vehicle_reg"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    registration_no: Mapped[str] = mapped_column(String(40))
    type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    capacity: Mapped[int] = mapped_column(Integer)
    insurance_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    fitness_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    permit_expires_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Driver(Base, TenantMixin, TimestampMixin):
    """A driver. person_id is the identity user id when the driver signs in (and is then the trip recorder)."""

    __tablename__ = f"{PREFIX}driver"
    __table_args__ = (Index("ix_transport_driver_person", "organisation_id", "person_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    licence_no: Mapped[str] = mapped_column(String(60))
    licence_expires_on: Mapped[date] = mapped_column(Date)
    phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Route(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}route"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_transport_route_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    direction: Mapped[str | None] = mapped_column(String(100), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    vehicle_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}vehicle.id"), nullable=True)
    driver_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}driver.id"), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class RouteStop(Base, TenantMixin):
    """A stop on a route, in order. Rows are replaced when the route's stops change."""

    __tablename__ = f"{PREFIX}route_stop"
    __table_args__ = (UniqueConstraint("organisation_id", "route_id", "stop_id", name="uq_transport_route_stop"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}route.id"), index=True)
    stop_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}stop.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    scheduled_time: Mapped[str | None] = mapped_column(String(5), nullable=True)


class Pass(Base, TenantMixin, TimestampMixin):
    """A pass request (status requested) or a pass (issued onwards)."""

    __tablename__ = f"{PREFIX}pass"
    __table_args__ = (
        Index("ix_transport_pass_person", "organisation_id", "person_id"),
        Index("ix_transport_pass_route_status", "organisation_id", "route_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    person_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    rider_type: Mapped[str] = mapped_column(String(10))
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}route.id"))
    stop_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}stop.id"))
    valid_from: Mapped[date] = mapped_column(Date)
    valid_to: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    capacity_override_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancelled_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Trip(Base, TenantMixin):
    __tablename__ = f"{PREFIX}trip"
    __table_args__ = (Index("ix_transport_trip_route_status", "organisation_id", "route_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    route_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}route.id"))
    vehicle_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}vehicle.id"))
    driver_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}driver.id"))
    status: Mapped[str] = mapped_column(String(10))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    started_by: Mapped[str] = mapped_column(String(36))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    delay_minutes: Mapped[int] = mapped_column(Integer, default=0)
    delay_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Position(Base, TenantMixin):
    """High volume and short lived: never published as an event, purged after the retention period."""

    __tablename__ = f"{PREFIX}position"
    __table_args__ = (Index("ix_transport_position_trip_time", "organisation_id", "trip_id", "recorded_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trip_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}trip.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    speed_kmh: Mapped[float | None] = mapped_column(Float, nullable=True)


class Notice(Base, TenantMixin):
    __tablename__ = f"{PREFIX}notice"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    route_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}route.id"), nullable=True)
    kind: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    published_by: Mapped[str] = mapped_column(String(36))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class DocumentFlag(Base, TenantMixin):
    """One row per document and expiry date the daily job has flagged, so transport.document.expiry-flagged goes
    out once per document. A renewed document has a new expiry date and is flagged again before it."""

    __tablename__ = f"{PREFIX}document_flag"
    __table_args__ = (
        UniqueConstraint("organisation_id", "subject_id", "document", "expires_on", name="uq_transport_document_flag"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subject: Mapped[str] = mapped_column(String(10))
    subject_id: Mapped[str] = mapped_column(String(36))
    document: Mapped[str] = mapped_column(String(20))
    expires_on: Mapped[date] = mapped_column(Date)
    flagged_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only, never personal details. Stands in for the audit SDK until it ships."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_transport_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Stop, Vehicle, Driver, Route, RouteStop, Pass, Trip, Position, Notice, DocumentFlag, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
