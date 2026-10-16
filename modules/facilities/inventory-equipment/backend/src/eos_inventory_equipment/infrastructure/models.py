"""Tables of inventory-equipment. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves
this module (a unit's asset_id is a plain reference to asset-management)."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "inventory_equipment_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    value = as_utc(value)
    return value.isoformat() if value else None


class Category(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}category"
    __table_args__ = (UniqueConstraint("organisation_id", "name", name="uq_inventory_equipment_category_name"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    approver_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    default_loan_rules: Mapped[dict] = mapped_column(JSON, default=dict)


class Location(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}location"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(120))
    address: Mapped[str | None] = mapped_column(String(300), nullable=True)
    keeper_user_ids: Mapped[list] = mapped_column(JSON, default=list)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Item(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}item"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_inventory_equipment_item_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    category_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}category.id"), index=True)
    tracking: Mapped[str] = mapped_column(String(20))
    unit_of_measure: Mapped[str] = mapped_column(String(30), default="piece")
    loanable: Mapped[bool] = mapped_column(Boolean, default=True)
    consumable: Mapped[bool] = mapped_column(Boolean, default=False)
    reorder_level: Mapped[float | None] = mapped_column(Float, nullable=True)
    reorder_quantity: Mapped[float | None] = mapped_column(Float, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    attributes: Mapped[dict] = mapped_column(JSON, default=dict)
    image_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    loan_rules: Mapped[dict] = mapped_column(JSON, default=dict)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    low_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Unit(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}unit"
    __table_args__ = (UniqueConstraint("organisation_id", "tag", name="uq_inventory_equipment_unit_tag"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}item.id"), index=True)
    tag: Mapped[str] = mapped_column(String(60))
    serial_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}location.id"), nullable=True)
    condition: Mapped[str] = mapped_column(String(20), default="good")
    status: Mapped[str] = mapped_column(String(20), default="available")
    asset_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    current_loan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class StockLevel(Base, TenantMixin):
    """On-hand and reserved quantity of a quantity-tracked item at one location."""

    __tablename__ = f"{PREFIX}stock_level"
    __table_args__ = (
        UniqueConstraint("organisation_id", "item_id", "location_id", name="uq_inventory_equipment_stock_level"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}item.id"), index=True)
    location_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}location.id"))
    on_hand: Mapped[float] = mapped_column(Float, default=0)
    reserved: Mapped[float] = mapped_column(Float, default=0)


class Movement(Base, TenantMixin, TimestampMixin):
    """Append-only stock ledger line. Never updated or deleted."""

    __tablename__ = f"{PREFIX}movement"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20), index=True)
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}item.id"), index=True)
    quantity: Mapped[float] = mapped_column(Float)
    unit_ids: Mapped[list] = mapped_column(JSON, default=list)
    from_location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    to_location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    issued_to: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    loan_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))


class Loan(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}loan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    borrower_id: Mapped[str] = mapped_column(String(36), index=True)
    requested_by: Mapped[str] = mapped_column(String(36))
    status: Mapped[str] = mapped_column(String(20), index=True)
    purpose: Mapped[str | None] = mapped_column(String(300), nullable=True)
    due_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handed_out_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    handed_out_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    extensions: Mapped[int] = mapped_column(Integer, default=0)
    reference: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class LoanLine(Base, TenantMixin):
    __tablename__ = f"{PREFIX}loan_line"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    loan_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}loan.id"), index=True)
    position: Mapped[int] = mapped_column(Integer, default=0)  # keeps the order the lines were requested in
    item_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}item.id"))
    quantity: Mapped[float] = mapped_column(Float, default=1)
    unit_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    from_location_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    condition_out: Mapped[str | None] = mapped_column(String(20), nullable=True)
    condition_in: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="waiting")  # waiting | out | returned | lost
    returned_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    damage_note: Mapped[str | None] = mapped_column(Text, nullable=True)


TABLES = [m.__table__ for m in (Category, Location, Item, Unit, StockLevel, Movement, Loan, LoanLine)]
