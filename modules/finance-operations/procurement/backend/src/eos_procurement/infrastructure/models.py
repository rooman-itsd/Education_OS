"""Tables of procurement. One shared schema with the procurement_ prefix; every table carries organisation_id
(TenantMixin) and gets the tenant_isolation row-level-security policy on Postgres. Money is Numeric(14, 2).
Nothing is deleted: indents are rejected, orders cancelled and invoices rejected, each with a reason. Items are kept
as JSON on their indent, quote, order or receipt, with quantities and prices as decimal strings."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import JSON, Date, DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "procurement_"
MONEY = Numeric(14, 2)


class Vendor(Base, TenantMixin, TimestampMixin):
    """A supplier. Only the last four digits of its bank account are kept (decided on #129)."""

    __tablename__ = f"{PREFIX}vendor"
    __table_args__ = (
        UniqueConstraint("organisation_id", "gstin", name="uq_procurement_vendor_gstin"),
        UniqueConstraint("organisation_id", "pan", name="uq_procurement_vendor_pan"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    categories: Mapped[list] = mapped_column(JSON)
    contact_name: Mapped[str] = mapped_column(String(200), default="")
    email: Mapped[str] = mapped_column(String(254), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    address: Mapped[str] = mapped_column(Text, default="")
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    pan: Mapped[str | None] = mapped_column(String(10), nullable=True)
    msme_registration: Mapped[str | None] = mapped_column(String(40), nullable=True)
    bank_account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)
    status_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Indent(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}indent"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_procurement_indent_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    justification: Mapped[str] = mapped_column(Text, default="")
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    line_id: Mapped[str] = mapped_column(String(36), index=True)  # a budget-grants line, never a foreign key
    items: Mapped[list] = mapped_column(JSON)
    estimated_cost: Mapped[Decimal] = mapped_column(MONEY)
    needed_by: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_ids: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    purchase_method: Mapped[str | None] = mapped_column(String(10), nullable=True)
    requested_by: Mapped[str] = mapped_column(String(36), index=True)
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Tender(Base, TenantMixin, TimestampMixin):
    """A quotation request or a tender for one or more approved indents on one line."""

    __tablename__ = f"{PREFIX}tender"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_procurement_tender_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20))
    title: Mapped[str] = mapped_column(String(300))
    method: Mapped[str] = mapped_column(String(10))
    line_id: Mapped[str] = mapped_column(String(36))
    category: Mapped[str] = mapped_column(String(100), default="")
    invited_vendor_ids: Mapped[list] = mapped_column(JSON)
    closes_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    terms: Mapped[str] = mapped_column(Text, default="")
    document_ids: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    awarded_quote_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    award_justification: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))


class Quote(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}quote"
    __table_args__ = (UniqueConstraint("tender_id", "vendor_id", name="uq_procurement_quote_vendor"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tender_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}tender.id"), index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}vendor.id"))
    items: Mapped[list] = mapped_column(JSON)
    total: Mapped[Decimal] = mapped_column(MONEY)
    delivery_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))


class PurchaseOrder(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}purchase_order"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_procurement_purchase_order_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20))
    vendor_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}vendor.id"), index=True)
    tender_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}tender.id"), nullable=True)
    line_id: Mapped[str] = mapped_column(String(36))
    items: Mapped[list] = mapped_column(JSON)
    delivery_by: Mapped[date] = mapped_column(Date)
    delivery_address: Mapped[str] = mapped_column(Text, default="")
    terms: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)
    subtotal: Mapped[Decimal] = mapped_column(MONEY)
    tax_total: Mapped[Decimal] = mapped_column(MONEY)
    total: Mapped[Decimal] = mapped_column(MONEY)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prepared_by: Mapped[str] = mapped_column(String(36))
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    issued_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class TenderIndent(Base, TenantMixin):
    """Which indents a tender buys for."""

    __tablename__ = f"{PREFIX}tender_indent"
    __table_args__ = (UniqueConstraint("tender_id", "indent_id", name="uq_procurement_tender_indent"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    tender_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}tender.id"), index=True)
    indent_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}indent.id"), index=True)


class OrderIndent(Base, TenantMixin):
    """Which indents a purchase order buys for."""

    __tablename__ = f"{PREFIX}order_indent"
    __table_args__ = (UniqueConstraint("purchase_order_id", "indent_id", name="uq_procurement_order_indent"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}purchase_order.id"), index=True)
    indent_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}indent.id"), index=True)


class GoodsReceipt(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}goods_receipt"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_procurement_goods_receipt_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(20))
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}purchase_order.id"), index=True)
    received_on: Mapped[date] = mapped_column(Date)
    delivery_note: Mapped[str] = mapped_column(Text, default="")
    items: Mapped[list] = mapped_column(JSON)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[str] = mapped_column(String(36))


class VendorInvoice(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}vendor_invoice"
    __table_args__ = (
        UniqueConstraint("organisation_id", "vendor_id", "invoice_number", name="uq_procurement_vendor_invoice_number"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    purchase_order_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}purchase_order.id"), index=True)
    vendor_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}vendor.id"), index=True)
    invoice_number: Mapped[str] = mapped_column(String(60))
    invoice_date: Mapped[date] = mapped_column(Date)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    tax_amount: Mapped[Decimal] = mapped_column(MONEY)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="recorded", index=True)
    recorded_by: Mapped[str] = mapped_column(String(36))
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    tds_deducted: Mapped[Decimal] = mapped_column(MONEY)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only. Stands in for the audit SDK until it ships, as in hostel, helpdesk and budget-grants."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_procurement_audit_entity", "organisation_id", "entity", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [
    m.__table__
    for m in (
        Vendor,
        Indent,
        Tender,
        Quote,
        PurchaseOrder,
        TenderIndent,
        OrderIndent,
        GoodsReceipt,
        VendorInvoice,
        AuditEntry,
    )
]
