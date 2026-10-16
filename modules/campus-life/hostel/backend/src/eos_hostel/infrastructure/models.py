"""Tables of hostel. Every table carries organisation_id (TenantMixin), so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this module.
person_id and user ids refer to identity / student-information by id only."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "hostel_"


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


class Hostel(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}hostel"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    occupancy_type: Mapped[str] = mapped_column(String(60))
    warden_ids: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Room(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}room"
    __table_args__ = (UniqueConstraint("organisation_id", "hostel_id", "number", name="uq_hostel_room_number"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    hostel_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}hostel.id"), index=True)
    number: Mapped[str] = mapped_column(String(40))
    floor: Mapped[str | None] = mapped_column(String(40), nullable=True)
    room_type: Mapped[str] = mapped_column(String(60))
    capacity: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="open")
    close_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Allocation(Base, TenantMixin, TimestampMixin):
    """A room request (status requested) or a bed allocation (confirmed onwards)."""

    __tablename__ = f"{PREFIX}allocation"
    __table_args__ = (
        Index("ix_hostel_allocation_person_year", "organisation_id", "person_id", "academic_year"),
        Index("ix_hostel_allocation_room_status", "organisation_id", "room_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    person_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    academic_year: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), index=True)
    preferred_hostel_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    preferred_room_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    hostel_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}hostel.id"), nullable=True)
    room_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}room.id"), nullable=True)
    bed: Mapped[str | None] = mapped_column(String(20), nullable=True)
    from_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    to_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    checked_in_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    checked_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    condition_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class MessMenu(Base, TenantMixin):
    __tablename__ = f"{PREFIX}mess_menu"
    __table_args__ = (
        UniqueConstraint("organisation_id", "hostel_id", "menu_date", "meal", name="uq_hostel_mess_menu_meal"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    hostel_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}hostel.id"), index=True)
    menu_date: Mapped[date] = mapped_column(Date)
    meal: Mapped[str] = mapped_column(String(60))
    items: Mapped[list] = mapped_column(JSON, default=list)
    updated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LeaveRequest(Base, TenantMixin, TimestampMixin):
    """Leave, including a short out-pass (day pass): from_at and to_at are date-times."""

    __tablename__ = f"{PREFIX}leave_request"
    __table_args__ = (Index("ix_hostel_leave_person", "organisation_id", "person_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    person_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    hostel_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}hostel.id"), index=True)
    from_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    to_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    destination: Mapped[str] = mapped_column(String(300))
    reason: Mapped[str] = mapped_column(Text)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Gate pass: security records the resident leaving and returning.
    departed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    departure_recorded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_recorded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # Set by the daily job when it publishes hostel.leave.overdue, so the event goes out once per leave.
    overdue_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Visit(Base, TenantMixin):
    """Personal data: never published as an event."""

    __tablename__ = f"{PREFIX}visit"
    __table_args__ = (Index("ix_hostel_visit_person", "organisation_id", "person_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    hostel_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}hostel.id"), index=True)
    person_id: Mapped[str] = mapped_column(String(36))
    visitor_name: Mapped[str] = mapped_column(String(200))
    relation: Mapped[str | None] = mapped_column(String(100), nullable=True)
    id_document_note: Mapped[str | None] = mapped_column(String(100), nullable=True)
    in_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))


class Incident(Base, TenantMixin, TimestampMixin):
    """Discipline incident. Restricted personal data: never published as an event."""

    __tablename__ = f"{PREFIX}incident"
    __table_args__ = (Index("ix_hostel_incident_person", "organisation_id", "person_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    hostel_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}hostel.id"), index=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    category: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="open")
    recorded_by: Mapped[str] = mapped_column(String(36))
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Notice(Base, TenantMixin):
    __tablename__ = f"{PREFIX}notice"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    hostel_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}hostel.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(120))
    body: Mapped[str] = mapped_column(Text)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    published_by: Mapped[str] = mapped_column(String(36))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    withdrawn_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only, never personal details. Stands in for the audit SDK until it ships."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_hostel_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Hostel, Room, Allocation, MessMenu, LeaveRequest, Visit, Incident, Notice, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
