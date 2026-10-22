"""Tables of helpdesk (PRD "Data model"). Every table carries organisation_id, so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module. requester_id, raised_by_id, assignee_id, member_ids, author_id and created_by are person ids from identity,
by id only. Lengths follow contracts/openapi.yaml where it gives a maximum."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "helpdesk_"


class Queue(Base, TenantMixin, TimestampMixin):
    """A support queue and the agents in it (contract Queue)."""

    __tablename__ = f"{PREFIX}queue"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_helpdesk_queue_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    member_ids: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Category(Base, TenantMixin, TimestampMixin):
    """A ticket category, or a sub-category when parent_id is set; two levels only (contract Category)."""

    __tablename__ = f"{PREFIX}category"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    parent_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}category.id"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(String(80))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_queue_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}queue.id"))
    default_priority: Mapped[str] = mapped_column(String(10))
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Ticket(Base, TenantMixin, TimestampMixin):
    """A ticket (contract Ticket). The open-by-priority counts read the index on (organisation_id, status,
    priority, queue_id) (PRD "Non-functional")."""

    __tablename__ = f"{PREFIX}ticket"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_helpdesk_ticket_number"),
        Index("ix_helpdesk_ticket_open_counts", "organisation_id", "status", "priority", "queue_id"),
        Index("ix_helpdesk_ticket_requester", "organisation_id", "requester_id"),
        Index("ix_helpdesk_ticket_assignee", "organisation_id", "assignee_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    requester_id: Mapped[str] = mapped_column(String(36))
    raised_by_id: Mapped[str] = mapped_column(String(36))
    channel: Mapped[str] = mapped_column(String(10))
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}category.id"))
    queue_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}queue.id"))
    assignee_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    priority: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(20), default="new")
    hold_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    attachment_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    duplicate_of: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}ticket.id"), nullable=True)
    reopen_count: Mapped[int] = mapped_column(Integer, default=0)
    satisfaction_rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    first_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Comment(Base, TenantMixin, TimestampMixin):
    """A public reply or an internal note on a ticket (contract Comment)."""

    __tablename__ = f"{PREFIX}comment"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}ticket.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36))
    author_is_requester: Mapped[bool] = mapped_column(Boolean, default=False)
    visibility: Mapped[str] = mapped_column(String(10))
    body: Mapped[str] = mapped_column(Text)
    attachment_document_ids: Mapped[list] = mapped_column(JSON, default=list)


class TicketLink(Base, TenantMixin, TimestampMixin):
    """A reference from a ticket to a record in another module, by name and id only (contract TicketLink)."""

    __tablename__ = f"{PREFIX}ticket_link"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "ticket_id", "module", "entity", "ref_id", name="uq_helpdesk_ticket_link_target"
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    ticket_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}ticket.id"), index=True)
    module: Mapped[str] = mapped_column(String(80))
    entity: Mapped[str] = mapped_column(String(80))
    ref_id: Mapped[str] = mapped_column(String(200))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))


class TicketNumberSequence(Base):
    """The last ticket number given in each organisation (PRD "TicketNumberSequence | organisation_id,
    last_number"). One row per organisation, keyed by organisation_id, which also carries the RLS policy."""

    __tablename__ = f"{PREFIX}ticket_number_sequence"

    organisation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "Every state change writes an audit record").
    Temporary, as agreed with the architecture lead for #113: stands in for the audit SDK and platform/audit until they
    ship, as hostel's does, and is not part of the platform audit trail. `reason` keeps the reason a caller gives where the
    contract asks for one to be "kept in the audit record" (PATCH /tickets/{id}) and for withdraw, cancel and reopen.
    Ticket titles, descriptions and replies are never copied here."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_helpdesk_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Queue, Category, Ticket, Comment, TicketLink, TicketNumberSequence, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
