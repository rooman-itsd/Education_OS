"""Tables of asset-management. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module (purchase, AMC and inventory unit references are plain values). Money is Numeric, never float."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "asset_management_"
MONEY = Numeric(14, 2)


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


class Category(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}category"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_asset_management_category_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    depreciation: Mapped[dict] = mapped_column(JSON, default=dict)
    verification_interval_months: Mapped[int | None] = mapped_column(Integer, nullable=True)


class Asset(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}asset"
    __table_args__ = (UniqueConstraint("organisation_id", "tag", name="uq_asset_management_asset_tag"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tag: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}category.id"), index=True)
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    make: Mapped[str | None] = mapped_column(String(100), nullable=True)
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    org_unit_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    custodian_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    condition: Mapped[str] = mapped_column(String(10), default="good")
    status: Mapped[str] = mapped_column(String(20), default="in_service", index=True)
    status_before_disposal: Mapped[str | None] = mapped_column(String(20), nullable=True)
    acquisition: Mapped[dict] = mapped_column(JSON, default=dict)  # date, supplier, invoice, funding, purchase ref
    cost: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3))
    in_service_date: Mapped[date] = mapped_column(Date)
    warranty_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    amc_reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    inventory_unit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    depreciation: Mapped[dict] = mapped_column(JSON, default=dict)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    photo_document_ids: Mapped[list] = mapped_column(JSON, default=list)
    accumulated_depreciation: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    depreciated_to: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_verified_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    overdue_notified_for: Mapped[date | None] = mapped_column(Date, nullable=True)
    disposed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Transfer(Base, TenantMixin, TimestampMixin):
    """Append-only history of location, department and custodian changes."""

    __tablename__ = f"{PREFIX}transfer"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}asset.id"), index=True)
    from_values: Mapped[dict] = mapped_column(JSON, default=dict)
    to_values: Mapped[dict] = mapped_column(JSON, default=dict)
    effective_on: Mapped[date] = mapped_column(Date)
    reason: Mapped[str] = mapped_column(Text)
    source: Mapped[str] = mapped_column(String(20), default="manual")
    recorded_by: Mapped[str] = mapped_column(String(36))


class Cycle(Base, TenantMixin, TimestampMixin):
    """A physical verification (audit) cycle."""

    __tablename__ = f"{PREFIX}cycle"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    due_on: Mapped[date] = mapped_column(Date)
    scope: Mapped[dict] = mapped_column(JSON, default=dict)
    verifier_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="planned", index=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class CycleLine(Base, TenantMixin):
    __tablename__ = f"{PREFIX}cycle_line"
    __table_args__ = (UniqueConstraint("cycle_id", "asset_id", name="uq_asset_management_cycle_line_asset"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cycle_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}cycle.id"), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}asset.id"))
    tag: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    expected_location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    result: Mapped[str] = mapped_column(String(20), default="pending")
    observed_location: Mapped[str | None] = mapped_column(String(300), nullable=True)
    condition: Mapped[str | None] = mapped_column(String(10), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    photo_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    verified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DepreciationRun(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}depreciation_run"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="draft")
    asset_count: Mapped[int] = mapped_column(Integer, default=0)
    total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3))
    by_category: Mapped[list] = mapped_column(JSON, default=list)
    category_ids: Mapped[list] = mapped_column(JSON, default=list)
    calculated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    posted_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class DepreciationLine(Base, TenantMixin):
    """One asset's depreciation for a run, or the catch-up taken when the asset was disposed (run_id empty)."""

    __tablename__ = f"{PREFIX}depreciation_line"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}depreciation_run.id"), index=True)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}asset.id"), index=True)
    category_id: Mapped[str] = mapped_column(String(36))
    tag: Mapped[str] = mapped_column(String(60))
    method: Mapped[str] = mapped_column(String(20))
    period_end: Mapped[date] = mapped_column(Date)
    opening_book_value: Mapped[Decimal] = mapped_column(MONEY)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    closing_book_value: Mapped[Decimal] = mapped_column(MONEY)
    kind: Mapped[str] = mapped_column(String(10), default="run")  # run | disposal


class Disposal(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}disposal"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    asset_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}asset.id"), index=True)
    method: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="requested", index=True)
    reason: Mapped[str] = mapped_column(Text)
    expected_proceeds: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    currency: Mapped[str] = mapped_column(String(3))
    requested_by: Mapped[str] = mapped_column(String(36), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    disposed_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    proceeds: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    book_value_at_disposal: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    gain_or_loss: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    recipient: Mapped[str | None] = mapped_column(String(300), nullable=True)
    certificate_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    completion_note: Mapped[str | None] = mapped_column(Text, nullable=True)


TABLES = [
    m.__table__ for m in (Category, Asset, Transfer, Cycle, CycleLine, DepreciationRun, DepreciationLine, Disposal)
]
