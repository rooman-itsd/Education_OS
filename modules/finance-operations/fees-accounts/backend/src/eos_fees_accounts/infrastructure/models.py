"""Tables of fees-accounts. One shared schema with the fees_accounts_ prefix; every table carries organisation_id
(TenantMixin) and gets the tenant_isolation row-level-security policy on Postgres. Money is Numeric(12, 2).
Nothing financial is deleted: invoices are cancelled, payments voided or refunded."""

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
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "fees_accounts_"
MONEY = Numeric(12, 2)
_NOT_CANCELLED = sql_text("status <> 'cancelled'")


class FeeHead(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}fee_head"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_fees_accounts_fee_head_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    category: Mapped[str] = mapped_column(String(20), default="other")
    refundable: Mapped[bool] = mapped_column(Boolean, default=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class FeeStructure(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}fee_structure"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    academic_year: Mapped[str] = mapped_column(String(9), index=True)
    programme_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    applies_to: Mapped[str] = mapped_column(String(10), default="student")
    category: Mapped[str | None] = mapped_column(String(60), nullable=True)
    room_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    route_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # [{"fee_head_id", "amount"}] and [{"label", "percent", "due_date"}], amounts and percents as decimal strings.
    items: Mapped[list] = mapped_column(JSON)
    instalments: Mapped[list] = mapped_column(JSON)
    allow_part_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    late_fee: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    total: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Invoice(Base, TenantMixin):
    __tablename__ = f"{PREFIX}invoice"
    __table_args__ = (
        UniqueConstraint("organisation_id", "number", name="uq_fees_accounts_invoice_number"),
        # One live invoice per person, structure and instalment; a cancelled one can be raised again.
        Index(
            "uq_fees_accounts_invoice_instalment",
            "organisation_id",
            "person_id",
            "fee_structure_id",
            "instalment",
            unique=True,
            sqlite_where=_NOT_CANCELLED,
            postgresql_where=_NOT_CANCELLED,
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    person_id: Mapped[str] = mapped_column(String(36), index=True)
    person_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    fee_structure_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}fee_structure.id"), nullable=True
    )
    instalment: Mapped[int | None] = mapped_column(Integer, nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(9), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    total: Mapped[Decimal] = mapped_column(MONEY)
    concession_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    late_fee: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    paid_total: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    status: Mapped[str] = mapped_column(String(20), default="issued", index=True)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    allow_part_payment: Mapped[bool] = mapped_column(Boolean, default=False)
    late_fee_rule: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    source_module: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    issued_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    late_fee_updated_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    overdue_notified: Mapped[bool] = mapped_column(Boolean, default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class InvoiceLine(Base, TenantMixin):
    __tablename__ = f"{PREFIX}invoice_line"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}invoice.id"), index=True)
    position: Mapped[int] = mapped_column(Integer)
    fee_head_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}fee_head.id"))
    fee_head_name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(String(300), default="")
    amount: Mapped[Decimal] = mapped_column(MONEY)


class Payment(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}payment"
    __table_args__ = (
        UniqueConstraint("organisation_id", "gateway_reference", name="uq_fees_accounts_payment_gateway"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}invoice.id"), index=True)
    person_id: Mapped[str] = mapped_column(String(36), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    refunded_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20), default="completed")
    gateway_reference: Mapped[str | None] = mapped_column(String(40), nullable=True)
    instrument_number: Mapped[str | None] = mapped_column(String(60), nullable=True)
    bank_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    paid_on: Mapped[date] = mapped_column(Date, index=True)
    receipt_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    void_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class Receipt(Base, TenantMixin):
    __tablename__ = f"{PREFIX}receipt"
    __table_args__ = (UniqueConstraint("organisation_id", "number", name="uq_fees_accounts_receipt_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    number: Mapped[str] = mapped_column(String(40))
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}payment.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}invoice.id"))
    person_id: Mapped[str] = mapped_column(String(36), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    status: Mapped[str] = mapped_column(String(10), default="valid")
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Refund(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}refund"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    payment_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}payment.id"), index=True)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}invoice.id"))
    person_id: Mapped[str] = mapped_column(String(36))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    mode: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(10), default="requested")
    reason: Mapped[str] = mapped_column(Text)
    gateway_refund_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Concession(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}concession"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    invoice_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}invoice.id"), index=True)
    person_id: Mapped[str] = mapped_column(String(36), index=True)
    kind: Mapped[str] = mapped_column(String(20))
    amount: Mapped[Decimal | None] = mapped_column(MONEY, nullable=True)
    percent: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    reason: Mapped[str] = mapped_column(Text)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="requested", index=True)
    approved_amount: Mapped[Decimal] = mapped_column(MONEY, default=Decimal("0"))
    requested_by: Mapped[str] = mapped_column(String(36))
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class NumberSequence(Base, TenantMixin):
    """The next invoice or receipt number of an organisation. Read FOR UPDATE, so numbers are never reused."""

    __tablename__ = f"{PREFIX}number_sequence"
    __table_args__ = (UniqueConstraint("organisation_id", "kind", name="uq_fees_accounts_number_sequence"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(10))
    last_value: Mapped[int] = mapped_column(Integer, default=0)


class BulkJob(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}bulk_job"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    fee_structure_id: Mapped[str] = mapped_column(String(36))
    instalment: Mapped[int] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="queued")
    requested: Mapped[int] = mapped_column(Integer, default=0)
    created: Mapped[int] = mapped_column(Integer, default=0)
    skipped: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[list] = mapped_column(JSON, default=list)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class CollectionTarget(Base, TenantMixin):
    __tablename__ = f"{PREFIX}collection_target"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    academic_year: Mapped[str] = mapped_column(String(9), index=True)
    period: Mapped[str] = mapped_column(String(7))
    fee_head_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)


class FeeSettings(Base, TenantMixin):
    __tablename__ = f"{PREFIX}settings"
    __table_args__ = (UniqueConstraint("organisation_id", name="uq_fees_accounts_settings_org"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    invoice_library_fines: Mapped[bool] = mapped_column(Boolean, default=False)
    invoice_staff_transport: Mapped[bool] = mapped_column(Boolean, default=False)


TABLES = [
    m.__table__
    for m in (
        FeeHead,
        FeeStructure,
        Invoice,
        InvoiceLine,
        Payment,
        Receipt,
        Refund,
        Concession,
        NumberSequence,
        BulkJob,
        CollectionTarget,
        FeeSettings,
    )
]
