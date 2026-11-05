"""Tables of placement-career. One shared schema with the placement_career_ prefix; every table carries
organisation_id (TenantMixin) and gets the tenant_isolation row-level-security policy on Postgres. Nothing is deleted
(PRD): drives and openings are cancelled or closed, applications rejected or withdrawn, and an application's history
only grows. Students and staff are platform/identity user ids, never foreign keys. Money is Numeric(14, 2)."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "placement_career_"
MONEY = Numeric(14, 2)


class Company(Base, TenantMixin, TimestampMixin):
    """A company the organisation places students with. A record, not a login. `name_key` is the name in lower case
    with single spaces: one company per name and organisation."""

    __tablename__ = f"{PREFIX}company"
    __table_args__ = (UniqueConstraint("organisation_id", "name_key", name="uq_placement_career_company_name"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    name_key: Mapped[str] = mapped_column(String(200))
    industry: Mapped[str | None] = mapped_column(String(120), nullable=True)
    website: Mapped[str | None] = mapped_column(String(500), nullable=True)
    contact_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    contact_email: Mapped[str | None] = mapped_column(String(254), nullable=True)
    contact_phone: Mapped[str | None] = mapped_column(String(40), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_by: Mapped[str] = mapped_column(String(36))


class Drive(Base, TenantMixin, TimestampMixin):
    """A dated campus event of one company: draft -> scheduled -> completed, or cancelled while no opening of it has
    applications. `rounds` and `eligibility` are shown, not tracked or enforced."""

    __tablename__ = f"{PREFIX}drive"
    __table_args__ = (Index("ix_placement_career_drive_status_date", "organisation_id", "status", "scheduled_on"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}company.id"), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    venue: Mapped[str | None] = mapped_column(String(300), nullable=True)
    registration_closes_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    rounds: Mapped[list] = mapped_column(JSON)
    eligibility: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))


class Opening(Base, TenantMixin, TimestampMixin):
    """A job (never an internship) in a drive of the same company or on its own: draft -> open -> closed, or cancelled
    while it has no applications. It takes applications up to and including applications_close_on (IST)."""

    __tablename__ = f"{PREFIX}opening"
    __table_args__ = (
        Index("ix_placement_career_opening_status_close", "organisation_id", "status", "applications_close_on"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    company_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}company.id"), index=True)
    drive_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}drive.id"), nullable=True, index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    ctc_per_annum: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    positions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    applications_close_on: Mapped[date] = mapped_column(Date)
    eligibility: Mapped[dict] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(12), default="draft")
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))


class Application(Base, TenantMixin):
    """A student's application to an opening, with their self-declaration (never checked by the system) and, from
    `offered` on, the offer. One per student and opening, a withdrawn one included."""

    __tablename__ = f"{PREFIX}application"
    __table_args__ = (UniqueConstraint("opening_id", "student_id", name="uq_placement_career_application_student"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    opening_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}opening.id"), index=True)
    student_id: Mapped[str] = mapped_column(String(36), index=True)
    student_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(12), default="applied", index=True)
    declares_eligible: Mapped[bool] = mapped_column(Boolean)
    declared_programme: Mapped[str | None] = mapped_column(String(200), nullable=True)
    declared_graduating_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    declared_cgpa: Mapped[Decimal | None] = mapped_column(Numeric(4, 2), nullable=True)
    declared_active_backlogs: Mapped[int | None] = mapped_column(Integer, nullable=True)
    offered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    offer_ctc_per_annum: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    offer_joining_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    offer_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    applied_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class ApplicationHistory(Base, TenantMixin):
    """One line per status an application reached, in order. Never edited or deleted."""

    __tablename__ = f"{PREFIX}application_history"
    __table_args__ = (UniqueConstraint("application_id", "sequence", name="uq_placement_career_history_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    application_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}application.id"), index=True)
    sequence: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(12))
    actor_id: Mapped[str] = mapped_column(String(36))
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (definition of done). Ids and the action only: never a
    declaration, an offer or a contact. Stands in for the audit SDK until it ships, as in e-office."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_placement_career_audit_entity", "organisation_id", "entity", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [m.__table__ for m in (Company, Drive, Opening, Application, ApplicationHistory, AuditEntry)]
