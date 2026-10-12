from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, Date, DateTime, Index, Integer, Numeric, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column

OPEN_STATUSES = ("created", "pending")
_OPEN_SQL = text("status IN ('created', 'pending')")
FINAL_STATUSES = ("succeeded", "failed", "expired", "refunded", "partially_refunded")
PAID_STATUSES = ("succeeded", "partially_refunded", "refunded")


def money(value: Decimal | None) -> str | None:
    return None if value is None else f"{Decimal(value):.2f}"


def iso(value: datetime | date | None) -> str | None:
    return value.isoformat() if value else None


class MerchantAccount(Base, TenantMixin):
    """An organisation's own SBIePay merchant account, used for fee payments. One per organisation."""

    __tablename__ = "payment_sbiepay_merchant_account"
    __table_args__ = (UniqueConstraint("organisation_id", name="uq_payment_sbiepay_merchant_org"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    merchant_id: Mapped[str] = mapped_column(String(100))
    mode: Mapped[str] = mapped_column(String(10))  # sandbox | live
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    # Stored encrypted once an AES library is approved; until then no key is ever stored.
    encryption_key_ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    def to_dict(self) -> dict:
        return {
            "merchant_id": self.merchant_id,
            "mode": self.mode,
            "active": self.active,
            "key_set": self.encryption_key_ciphertext is not None,
            "updated_at": iso(self.updated_at),
        }


class Payment(Base, TenantMixin, TimestampMixin):
    __tablename__ = "payment_sbiepay_payment"
    # At most one open payment per caller source in an organisation, enforced by the database so two
    # simultaneous requests cannot both start a payment for the same invoice.
    __table_args__ = (
        Index(
            "uq_payment_sbiepay_open_source",
            "organisation_id",
            "source_module",
            "source_reference",
            unique=True,
            sqlite_where=_OPEN_SQL,
            postgresql_where=_OPEN_SQL,
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(40), unique=True, index=True)
    purpose: Mapped[str] = mapped_column(String(20))  # subscription | fee
    source_module: Mapped[str] = mapped_column(String(60), index=True)
    source_reference: Mapped[str] = mapped_column(String(100), index=True)
    merchant_id: Mapped[str] = mapped_column(String(100))
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    refunded_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0"))
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    description: Mapped[str] = mapped_column(String(100), default="")
    payer: Mapped[dict] = mapped_column(JSON, default=dict)
    return_url: Mapped[str] = mapped_column(String(2000))
    notify_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="created", index=True)
    gateway_transaction_id: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    payment_mode: Mapped[str | None] = mapped_column(String(40), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    initiated_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    settled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reference": self.reference,
            "organisation_id": self.organisation_id,
            "purpose": self.purpose,
            "source_module": self.source_module,
            "source_reference": self.source_reference,
            "amount": money(self.amount),
            "refunded_amount": money(self.refunded_amount),
            "currency": self.currency,
            "status": self.status,
            "gateway_transaction_id": self.gateway_transaction_id,
            "payment_mode": self.payment_mode,
            "failure_reason": self.failure_reason,
            "created_at": iso(self.created_at),
            "completed_at": iso(self.completed_at),
        }


class Refund(Base, TenantMixin):
    __tablename__ = "payment_sbiepay_refund"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    payment_id: Mapped[str] = mapped_column(String(36), index=True)
    reference: Mapped[str] = mapped_column(String(40), index=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    reason: Mapped[str] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(20), default="requested")  # requested | succeeded | failed
    gateway_refund_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    failure_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "reference": self.reference,
            "amount": money(self.amount),
            "status": self.status,
            "gateway_refund_id": self.gateway_refund_id,
            "requested_at": iso(self.requested_at),
        }


class ReconciliationRun(Base, TenantMixin):
    __tablename__ = "payment_sbiepay_reconciliation_run"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    settlement_date: Mapped[date] = mapped_column(Date, index=True)
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued | running | completed | failed
    matched: Mapped[int] = mapped_column(Integer, default=0)
    mismatches: Mapped[list] = mapped_column(JSON, default=list)
    failure_reason: Mapped[str | None] = mapped_column(String(300), nullable=True)
    requested_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "settlement_date": iso(self.settlement_date),
            "status": self.status,
            "matched": self.matched,
            "mismatches": list(self.mismatches or []),
            "started_at": iso(self.started_at),
            "finished_at": iso(self.finished_at),
        }


class Notification(Base, TenantMixin, TimestampMixin):
    """A signed PaymentNotification waiting to be delivered to a caller's notify_url, retried with backoff."""

    __tablename__ = "payment_sbiepay_notification"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36), unique=True)
    payment_id: Mapped[str] = mapped_column(String(36), index=True)
    url: Mapped[str] = mapped_column(String(2000))
    body: Mapped[dict] = mapped_column(JSON)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[str | None] = mapped_column(String(300), nullable=True)
