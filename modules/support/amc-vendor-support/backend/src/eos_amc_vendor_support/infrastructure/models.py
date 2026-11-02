"""Tables of amc-vendor-support (PRD "Data model"). Every table carries organisation_id, so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name and no foreign key leaves this
module: vendor_id is a procurement vendor, owner_id and raised_by person ids from identity, and references point to
records in other modules, all by id only (PRD "Rules")."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "amc_vendor_support_"


class Contract(Base, TenantMixin, TimestampMixin):
    """An AMC contract (contract Contract). Stored status is draft, active, terminated or renewed; expiring and
    expired are worked out when read. renewed_from_id and renewed_to_id link a contract and its one renewal."""

    __tablename__ = f"{PREFIX}contract"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_amc_vendor_support_contract_number"),
        Index("ix_amc_vendor_support_contract_status_end", "organisation_id", "status", "end_date"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    vendor_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    coverage_type: Mapped[str] = mapped_column(String(20))
    scope: Mapped[str | None] = mapped_column(Text, nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    value_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    value_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    purchase_order_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    response_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    resolution_hours: Mapped[int | None] = mapped_column(Integer, nullable=True)
    preventive_visits_per_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    vendor_contacts: Mapped[list] = mapped_column(JSON, default=list)
    owner_id: Mapped[str] = mapped_column(String(36))
    renewal_notice_days: Mapped[int] = mapped_column(Integer, default=60)
    status: Mapped[str] = mapped_column(String(12))
    renewed_from_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    renewed_to_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    termination_effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    termination_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class CoveredItem(Base, TenantMixin, TimestampMixin):
    """Something a contract covers (contract CoveredItem). The optional reference, such as an asset in
    asset-management, is kept in three columns so GET /coverage can find it and the same reference cannot be covered
    twice by one contract."""

    __tablename__ = f"{PREFIX}covered_item"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id",
            "contract_id",
            "ref_module",
            "ref_entity",
            "ref_id",
            name="uq_amc_vendor_support_covered_item_reference",
        ),
        Index("ix_amc_vendor_support_covered_item_reference", "organisation_id", "ref_module", "ref_entity", "ref_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}contract.id"), index=True)
    description: Mapped[str] = mapped_column(String(200))
    ref_module: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ref_entity: Mapped[str | None] = mapped_column(String(60), nullable=True)
    ref_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Engagement(Base, TenantMixin, TimestampMixin):
    """A breakdown call or preventive visit made to the vendor under a contract (contract Engagement)."""

    __tablename__ = f"{PREFIX}engagement"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_amc_vendor_support_engagement_number"),
        Index("ix_amc_vendor_support_engagement_contract", "organisation_id", "contract_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    contract_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}contract.id"))
    kind: Mapped[str] = mapped_column(String(20))
    description: Mapped[str] = mapped_column(Text)
    covered_item_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    references: Mapped[list] = mapped_column(JSON, default=list)
    vendor_call_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(12))
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    vendor_responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    raised_by: Mapped[str] = mapped_column(String(36))
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class NumberSequence(Base):
    """The last number given per organisation and kind ("contract" for AMC-000012, "engagement" for AVS-000034).
    Keyed by organisation_id, which also carries the RLS policy, and kind."""

    __tablename__ = f"{PREFIX}number_sequence"

    organisation_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    kind: Mapped[str] = mapped_column(String(20), primary_key=True)
    last_number: Mapped[int] = mapped_column(Integer, default=0)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change of contracts, covered items and engagements (PRD rule "Every
    state change writes an audit record"). Stands in for the audit SDK, which does not exist yet (packages/sdk is
    empty), as helpdesk's and hostel's do; its rows are not in the platform audit trail. `reason` keeps the reason a
    caller gives (terminate, cancel). Scope text, contacts and engagement notes are never copied here."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_amc_vendor_support_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Contract, CoveredItem, Engagement, NumberSequence, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
