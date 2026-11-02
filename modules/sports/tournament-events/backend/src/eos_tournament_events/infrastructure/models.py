"""Tables of tournament-events. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module (athlete, discipline, user and contact ids are plain values)."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "tournament_events_"


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


class Tournament(Base, TenantMixin, TimestampMixin, _Updated):
    """`status` stores draft, published or cancelled; ongoing and completed follow from the dates
    (domain.rules.effective_status)."""

    __tablename__ = f"{PREFIX}tournament"
    __table_args__ = (Index("ix_tournament_events_tournament_dates", "organisation_id", "start_date", "end_date"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    discipline: Mapped[str] = mapped_column(String(120))
    discipline_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    level: Mapped[str] = mapped_column(String(30))
    format: Mapped[str] = mapped_column(String(30))
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    hosting: Mapped[str | None] = mapped_column(String(10), nullable=True)
    registration_closes_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancellation_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Entry(Base, TenantMixin, TimestampMixin, _Updated):
    """An athlete or a team in one category. athlete_ids are athlete-performance athlete ids."""

    __tablename__ = f"{PREFIX}entry"
    __table_args__ = (Index("ix_tournament_events_entry_tournament", "tournament_id", "category"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tournament_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}tournament.id"))
    category: Mapped[str] = mapped_column(String(120))
    team_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    athlete_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20))


class Fixture(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}fixture"
    __table_args__ = (Index("ix_tournament_events_fixture_tournament", "tournament_id", "scheduled_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tournament_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}tournament.id"))
    round: Mapped[str] = mapped_column(String(120))
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    entry_ids: Mapped[list] = mapped_column(JSON, default=list)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    status: Mapped[str] = mapped_column(String(20))


class Official(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}official"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tournament_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}tournament.id"), index=True)
    fixture_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}fixture.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    official_role: Mapped[str] = mapped_column(String(30))
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False)


class Result(Base, TenantMixin, TimestampMixin, _Updated):
    """One result per fixture; recording again replaces the placings (the audit entry keeps who did it)."""

    __tablename__ = f"{PREFIX}result"
    __table_args__ = (UniqueConstraint("organisation_id", "fixture_id", name="uq_tournament_events_result_fixture"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tournament_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}tournament.id"), index=True)
    fixture_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}fixture.id"))
    placings: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Logistics(Base, TenantMixin, _Updated):
    """Travel and event logistics, one per tournament."""

    __tablename__ = f"{PREFIX}logistics"
    __table_args__ = (
        UniqueConstraint("organisation_id", "tournament_id", name="uq_tournament_events_logistics_tournament"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tournament_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}tournament.id"))
    travel_mode: Mapped[str | None] = mapped_column(String(10), nullable=True)
    departure_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    return_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accommodation: Mapped[str | None] = mapped_column(Text, nullable=True)
    travelling_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    contact_person_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AthleteLink(Base, TenantMixin):
    """Which platform/identity user is which athlete, learnt from athlete-performance.athlete.registered and
    athlete.updated, so an athlete sees only their own entries without this module importing athlete-performance.
    user_id is empty once the athlete's user was removed; linked_at is the occurred_at of the event that set it."""

    __tablename__ = f"{PREFIX}athlete_link"
    __table_args__ = (UniqueConstraint("organisation_id", "athlete_id", name="uq_tournament_events_link_athlete"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when. Interim, until the audit SDK ships: the columns follow platform/audit's `Record`,
    as athlete-performance's audit table does, so each row can be backfilled with its `client_token`. `before` and
    `after` hold changed fields only, never free text (descriptions, notes, reasons, accommodation)."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_tournament_events_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_tournament_events_audit_client_token"),
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


TABLES = [m.__table__ for m in (Tournament, Entry, Fixture, Official, Result, Logistics, AthleteLink, AuditEntry)]
