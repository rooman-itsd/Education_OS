"""Tables of regulatory-reports (PRD "Data model"). Every table carries organisation_id, so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module: default_owner_id, owner_id and submitted_by are person ids from identity, by id only."""

from __future__ import annotations

from datetime import date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "regulatory_reports_"

# Column sizes, shared with the request schemas so a value too long is a 422, never a database error.
TITLE_LEN = 200  # Obligation.title, Link.title
AUTHORITY_LEN = 120  # Obligation.authority
URL_LEN = 2000  # Obligation.portal_url, Link.url
PERIOD_LABEL_LEN = 60  # Filing.period_label
REFERENCE_LEN = 120  # submission_reference, acknowledgement_reference


class Obligation(Base, TenantMixin, TimestampMixin):
    """A return the organisation must file (contract Obligation). Deactivated, never deleted."""

    __tablename__ = f"{PREFIX}obligation"
    __table_args__ = (Index("ix_regulatory_reports_obligation_title", "organisation_id", "title"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(TITLE_LEN))
    authority: Mapped[str] = mapped_column(String(AUTHORITY_LEN))
    portal_url: Mapped[str | None] = mapped_column(String(URL_LEN), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    recurrence: Mapped[str] = mapped_column(String(12))
    default_owner_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Filing(Base, TenantMixin, TimestampMixin):
    """The filing of an obligation for one period (contract Filing). One per obligation and period label. Overdue and
    due soon are worked out when read, never stored."""

    __tablename__ = f"{PREFIX}filing"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "obligation_id", "period_label", name="uq_regulatory_reports_filing_period"
        ),
        Index("ix_regulatory_reports_filing_status_due", "organisation_id", "status", "due_on"),
        Index("ix_regulatory_reports_filing_owner", "organisation_id", "owner_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    obligation_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}obligation.id"), index=True)
    period_label: Mapped[str] = mapped_column(String(PERIOD_LABEL_LEN))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    due_on: Mapped[date] = mapped_column(Date)
    owner_id: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(16))
    preparation_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    links: Mapped[list] = mapped_column(JSON, default=list)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    submission_reference: Mapped[str | None] = mapped_column(String(REFERENCE_LEN), nullable=True)
    submitted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    acknowledged_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    acknowledgement_reference: Mapped[str | None] = mapped_column(String(REFERENCE_LEN), nullable=True)
    not_applicable_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every obligation and filing change (PRD rule "Every state change ... writes an
    audit record"). Stands in for the audit SDK, which does not exist yet (packages/sdk is empty), as amc-vendor-support's
    does; its rows are not in the platform audit trail. `reason` keeps a return comment or a not-applicable reason.
    Preparation notes, links and submission and acknowledgement references are never copied here."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_regulatory_reports_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Obligation, Filing, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
