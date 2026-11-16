"""Tables of incident-management (PRD "Data model"). Every table carries organisation_id, so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module: lead, responder, reporter, owner and author ids are person ids from identity, attachment ids are documents
in platform/documents, and references point to records in other modules, all by id only (PRD "Rules")."""

from __future__ import annotations

from datetime import date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "incident_management_"


class Problem(Base, TenantMixin, TimestampMixin):
    """The cause behind one or more incidents (contract Problem). Incidents point to it with problem_id."""

    __tablename__ = f"{PREFIX}problem"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_incident_management_problem_number"),
        Index("ix_incident_management_problem_status", "organisation_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    affected_services: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(16))
    owner_id: Mapped[str] = mapped_column(String(36))
    workaround: Mapped[str | None] = mapped_column(Text, nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Incident(Base, TenantMixin, TimestampMixin):
    """An unplanned disruption of a service (contract Incident). An incident links to at most one problem."""

    __tablename__ = f"{PREFIX}incident"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_incident_management_incident_number"),
        Index("ix_incident_management_incident_status", "organisation_id", "status", "severity"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text)
    affected_services: Mapped[list] = mapped_column(JSON, default=list)
    severity: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(16))
    lead_id: Mapped[str] = mapped_column(String(36))
    responder_ids: Mapped[list] = mapped_column(JSON, default=list)
    reported_by: Mapped[str] = mapped_column(String(36))
    problem_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}problem.id"), nullable=True)
    resolution_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    mitigated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class TimelineUpdate(Base, TenantMixin, TimestampMixin):
    """One entry of an incident's timeline (contract TimelineUpdate), including the notes given when an incident is
    cancelled or reopened."""

    __tablename__ = f"{PREFIX}timeline_update"
    __table_args__ = (Index("ix_incident_management_timeline_incident", "organisation_id", "incident_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}incident.id"))
    author_id: Mapped[str] = mapped_column(String(36))
    body: Mapped[str] = mapped_column(Text)


class Reference(Base, TenantMixin, TimestampMixin):
    """A record in another module related to an incident (contract Reference), by id only. The same record is
    recorded once per incident."""

    __tablename__ = f"{PREFIX}reference"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "incident_id",
            "ref_module",
            "ref_entity",
            "ref_id",
            name="uq_incident_management_reference_record",
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    incident_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}incident.id"), index=True)
    ref_module: Mapped[str] = mapped_column(String(60))
    ref_entity: Mapped[str] = mapped_column(String(60))
    ref_id: Mapped[str] = mapped_column(String(100))
    relation: Mapped[str] = mapped_column(String(20))
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))


class Rca(Base, TenantMixin):
    """A problem's root-cause analysis (contract Rca): at most one per problem, keyed by problem_id."""

    __tablename__ = f"{PREFIX}rca"

    problem_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}problem.id"), primary_key=True)
    summary: Mapped[str] = mapped_column(Text)
    root_cause: Mapped[str] = mapped_column(Text)
    contributing_factors: Mapped[list] = mapped_column(JSON, default=list)
    attachment_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(10))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    published_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CorrectiveAction(Base, TenantMixin, TimestampMixin):
    """An action that follows from a problem's RCA (contract CorrectiveAction). The optional reference, such as a
    maintenance work order, is kept as the contract's ReferenceInput."""

    __tablename__ = f"{PREFIX}corrective_action"
    __table_args__ = (
        Index("ix_incident_management_action_due", "organisation_id", "status", "due_date"),
        Index("ix_incident_management_action_owner", "organisation_id", "owner_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    problem_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}problem.id"), index=True)
    description: Mapped[str] = mapped_column(Text)
    owner_id: Mapped[str] = mapped_column(String(36))
    due_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(10))
    reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NumberSequence(Base):
    """The last number given per organisation and kind ("incident" for INC-000123, "problem" for PRB-000045).
    Keyed by organisation_id, which also carries the RLS policy, and kind."""

    __tablename__ = f"{PREFIX}number_sequence"

    organisation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change, timeline update, reference change, problem link, RCA
    publication and action change (PRD "Rules"). Stands in for the audit SDK, which does not exist yet (packages/sdk
    is empty), as amc-vendor-support's and helpdesk's do; its rows are not in the platform audit trail. `reason` keeps
    which fields changed or the problem an incident was linked to. Titles, descriptions, timeline text and RCA text
    are never copied here."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_incident_management_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Problem, Incident, TimelineUpdate, Reference, Rca, CorrectiveAction, NumberSequence, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
