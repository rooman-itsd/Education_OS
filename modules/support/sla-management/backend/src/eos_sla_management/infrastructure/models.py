"""Tables of sla-management (PRD "Data model"). Every table carries organisation_id, so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module: ticket, category, queue and assignee ids are helpdesk's and identity's, kept by id only. No ticket title,
description or reply is ever stored (PRD "Rules")."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "sla_management_"


class Calendar(Base, TenantMixin, TimestampMixin):
    """A business-hours calendar (contract Calendar). working_hours is a list of {weekday, start, end} and holidays a
    list of {date, name}, both as the contract shows them."""

    __tablename__ = f"{PREFIX}calendar"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    time_zone: Mapped[str] = mapped_column(String(64))
    always_open: Mapped[bool] = mapped_column(Boolean, default=False)
    working_hours: Mapped[list] = mapped_column(JSON, default=list)
    holidays: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Policy(Base, TenantMixin, TimestampMixin):
    """An SLA policy for one priority and one helpdesk category or every category (contract Policy). category_key is
    the category id or "*", so the partial unique index allows one active policy per (priority, category) pair,
    "every category" included, also when two requests race."""

    __tablename__ = f"{PREFIX}policy"
    __table_args__ = (
        Index(
            "uq_sla_management_policy_active",
            "organisation_id",
            "priority",
            "category_key",
            unique=True,
            sqlite_where=text("active"),
            postgresql_where=text("active"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(10))
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    category_key: Mapped[str] = mapped_column(String(36))
    calendar_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}calendar.id"), index=True)
    response_target_minutes: Mapped[int] = mapped_column(Integer)
    resolution_target_minutes: Mapped[int] = mapped_column(Integer)
    warning_percent: Mapped[int] = mapped_column(Integer)
    pause_on_hold_reasons: Mapped[list] = mapped_column(JSON, default=list)
    escalation_levels: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TicketRef(Base, TenantMixin, TimestampMixin):
    """What sla-management knows of a helpdesk ticket, cached from helpdesk's events (PRD TicketRef). One row per
    ticket; every event for the ticket locks it first, so one ticket's events are applied one at a time. created is
    false while only an earlier helpdesk.ticket.assigned is known; final is set by closed or cancelled."""

    __tablename__ = f"{PREFIX}ticket_ref"
    __table_args__ = (UniqueConstraint("organisation_id", "ticket_id", name="uq_sla_management_ticket_ref_ticket"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(String(36))
    number: Mapped[str | None] = mapped_column(String(40), nullable=True)
    priority: Mapped[str | None] = mapped_column(String(10), nullable=True)
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    queue_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    created: Mapped[bool] = mapped_column(Boolean, default=False)
    final: Mapped[bool] = mapped_column(Boolean, default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Clock(Base, TenantMixin, TimestampMixin):
    """A response or resolution clock of one ticket (contract Clock). The policy's targets, warning percent, pausing
    hold reasons and escalation levels are copied when the clock starts or is recalculated (PRD "Rules").

    business_minutes_used is the business time counted up to run_started_at (while running) or up to the pause or
    stop; the live figure adds the time since run_started_at. escalated_level is the last level fired and
    next_escalation_at when the next one is due."""

    __tablename__ = f"{PREFIX}clock"
    __table_args__ = (
        UniqueConstraint("organisation_id", "ticket_id", "kind", name="uq_sla_management_clock_ticket_kind"),
        Index("ix_sla_management_clock_state_due", "organisation_id", "state", "due_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(String(36))
    ticket_number: Mapped[str] = mapped_column(String(40))
    kind: Mapped[str] = mapped_column(String(10))
    policy_id: Mapped[str] = mapped_column(String(36))
    calendar_id: Mapped[str] = mapped_column(String(36))
    priority: Mapped[str] = mapped_column(String(10))
    category_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    queue_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    assignee_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    target_minutes: Mapped[int] = mapped_column(Integer)
    warning_percent: Mapped[int] = mapped_column(Integer)
    pause_on_hold_reasons: Mapped[list] = mapped_column(JSON, default=list)
    escalation_levels: Mapped[list] = mapped_column(JSON, default=list)
    business_minutes_used: Mapped[int] = mapped_column(Integer, default=0)
    run_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    state: Mapped[str] = mapped_column(String(10))
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    warn_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paused_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    stopped_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(10), nullable=True)
    warned: Mapped[bool] = mapped_column(Boolean, default=False)
    breached: Mapped[bool] = mapped_column(Boolean, default=False)
    breached_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    escalated_level: Mapped[int] = mapped_column(Integer, default=0)
    next_escalation_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Escalation(Base, TenantMixin, TimestampMixin):
    """One escalation level fired for a breached clock (contract Escalation)."""

    __tablename__ = f"{PREFIX}escalation"
    __table_args__ = (UniqueConstraint("organisation_id", "clock_id", "level", name="uq_sla_management_escalation"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    clock_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}clock.id"), index=True)
    level: Mapped[int] = mapped_column(Integer)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    recipient_ids: Mapped[list] = mapped_column(JSON, default=list)


class ProcessedEvent(Base, TenantMixin):
    """A helpdesk event already applied, by its envelope id (PRD "Each helpdesk event is applied once, by event id")."""

    __tablename__ = f"{PREFIX}processed_event"
    __table_args__ = (UniqueConstraint("organisation_id", "event_id", name="uq_sla_management_processed_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(120))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every change of calendars and policies and every state change and escalation of
    a clock (PRD rule "Every state change and every escalation writes an audit record"). Stands in for the audit SDK,
    which does not exist yet (packages/sdk is empty), as helpdesk's and amc-vendor-support's do. actor is null for
    changes driven by helpdesk's events; reason then names the event."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_sla_management_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Calendar, Policy, TicketRef, Clock, Escalation, ProcessedEvent, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
