from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column


class Plan(Base):
    """Plans are platform-wide data (not tenant-scoped). Seeded from config/plans.yaml; super admin edits them."""

    __tablename__ = "billing_plan"
    id: Mapped[str] = mapped_column(String(40), primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    description: Mapped[str] = mapped_column(String(500), default="")
    price_per_month: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    trial_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    suites: Mapped[list] = mapped_column(JSON, default=list)
    modules: Mapped[list] = mapped_column(JSON, default=list)
    specialized_suites: Mapped[str] = mapped_column(String(10), default="0")  # number or "all"
    integrations: Mapped[list] = mapped_column(JSON, default=list)
    limits: Mapped[dict] = mapped_column(JSON, default=dict)
    after_trial: Mapped[str] = mapped_column(String(20), default="read_only")
    published: Mapped[bool] = mapped_column(Boolean, default=True)

    def to_rule(self) -> dict:
        """The shape eos_core.entitlement.compute_entitlement expects."""
        ss = self.specialized_suites
        return {
            "id": self.id,
            "suites": list(self.suites or []),
            "modules": list(self.modules or []),
            "specialized_suites": "all" if ss == "all" else int(ss),
            "integrations": list(self.integrations or []),
            "limits": dict(self.limits or {}),
        }

    def to_dict(self) -> dict:
        return {
            **self.to_rule(),
            "title": self.title,
            "description": self.description,
            "price_per_month": float(self.price_per_month or 0),
            "currency": self.currency,
            "trial_days": self.trial_days,
            "after_trial": self.after_trial,
            "published": self.published,
        }


class Subscription(Base, TenantMixin, TimestampMixin):
    __tablename__ = "billing_subscription"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(
        String(20), default="trialing"
    )  # trialing | active | past_due | cancelled | read_only
    trial_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    current_period_ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    comped_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    pending_plan_id: Mapped[str | None] = mapped_column(String(40), nullable=True)
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "plan": self.plan_id,
            "status": self.status,
            "trial_ends_at": self.trial_ends_at.isoformat() if self.trial_ends_at else None,
            "current_period_ends_at": self.current_period_ends_at.isoformat() if self.current_period_ends_at else None,
            "pending_plan": self.pending_plan_id,
        }


class Invoice(Base, TenantMixin, TimestampMixin):
    """One charge for a subscription period. Written when a paid plan is activated (payment confirmed, or
    activated at once when no payment adapter is configured); the PDF in platform/documents comes later."""

    __tablename__ = "billing_invoice"
    __table_args__ = (UniqueConstraint("invoice_number", name="uq_billing_invoice_number"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    subscription_id: Mapped[str] = mapped_column(String(36), index=True)
    plan_id: Mapped[str] = mapped_column(String(40))
    amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    currency: Mapped[str] = mapped_column(String(3), default="INR")
    status: Mapped[str] = mapped_column(String(10), default="paid")  # draft | due | paid | void
    issued_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    payment_reference: Mapped[str | None] = mapped_column(String(100), nullable=True)
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    # GST tax invoice (contract 0.3.0). A snapshot taken when the invoice is issued, never recomputed: a later
    # change of the organisation's profile or of the rate does not touch an invoice already issued. Null on an
    # invoice issued before GST invoicing existed. `amount` stays the taxable value, so revenue excludes GST.
    invoice_number: Mapped[str | None] = mapped_column(String(16), nullable=True)
    financial_year: Mapped[str | None] = mapped_column(String(5), nullable=True)
    tax_scheme: Mapped[str | None] = mapped_column(String(5), nullable=True)  # intra | inter | none
    sac_code: Mapped[str | None] = mapped_column(String(6), nullable=True)
    gst_rate: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    taxable_value: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cgst_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    sgst_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    igst_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    total_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    place_of_supply: Mapped[str | None] = mapped_column(String(2), nullable=True)  # state code
    supplier_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    supplier_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    supplier_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    supplier_state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)
    recipient_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    recipient_gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    recipient_address: Mapped[str | None] = mapped_column(String(500), nullable=True)
    recipient_state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    def to_dict(self) -> dict:
        def dec(v: Decimal | None) -> str | None:
            return None if v is None else f"{Decimal(v):.2f}"

        return {
            "id": self.id,
            "organisation_id": self.organisation_id,
            "plan": self.plan_id,
            "amount": float(self.amount or 0),
            "currency": self.currency,
            "status": self.status,
            "issued_at": self.issued_at.isoformat() if self.issued_at else None,
            "period_start": self.period_start.isoformat() if self.period_start else None,
            "period_end": self.period_end.isoformat() if self.period_end else None,
            "payment_reference": self.payment_reference,
            "document_id": self.document_id,
            "invoice_number": self.invoice_number,
            "financial_year": self.financial_year,
            "tax_scheme": self.tax_scheme,
            "sac_code": self.sac_code,
            "gst_rate": None if self.gst_rate is None else f"{Decimal(self.gst_rate):.2f}",
            "taxable_value": dec(self.taxable_value),
            "cgst_amount": dec(self.cgst_amount),
            "sgst_amount": dec(self.sgst_amount),
            "igst_amount": dec(self.igst_amount),
            "total_amount": dec(self.total_amount),
            "place_of_supply": self.place_of_supply,
            "supplier": {
                "name": self.supplier_name,
                "gstin": self.supplier_gstin,
                "address": self.supplier_address,
                "state_code": self.supplier_state_code,
            },
            "recipient": {
                "name": self.recipient_name,
                "gstin": self.recipient_gstin,
                "address": self.recipient_address,
                "state_code": self.recipient_state_code,
            },
        }


class InvoiceCounter(Base):
    """The last invoice sequence used in a financial year ('26-27'). Platform-wide, like Plan: the platform is
    the one supplier, and GST numbering is one series per registration. The row is locked while a number is
    taken and the number is written in the same transaction as its invoice, so a failed activation rolls the
    counter back and no number is ever skipped or reused."""

    __tablename__ = "billing_invoice_counter"
    financial_year: Mapped[str] = mapped_column(String(5), primary_key=True)
    last_sequence: Mapped[int] = mapped_column(Integer, default=0)


class BillingProfile(Base, TenantMixin, TimestampMixin):
    """Who an organisation's invoices are addressed to (the GST recipient). One row per organisation. The GSTIN
    is optional: without one the invoice is business-to-consumer."""

    __tablename__ = "billing_profile"
    __table_args__ = (UniqueConstraint("organisation_id", name="uq_billing_profile_organisation"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    legal_name: Mapped[str] = mapped_column(String(200), default="")
    gstin: Mapped[str | None] = mapped_column(String(15), nullable=True)
    address: Mapped[str] = mapped_column(String(500), default="")
    state_code: Mapped[str | None] = mapped_column(String(2), nullable=True)

    def to_dict(self) -> dict:
        return {
            "organisation_id": self.organisation_id,
            "legal_name": self.legal_name,
            "gstin": self.gstin,
            "address": self.address,
            "state_code": self.state_code,
        }


class TrialReminder(Base, TenantMixin):
    """A trial reminder already raised: one row per organisation, trial end date and threshold (7, 3 or 1 days).
    remind_trials() raises the most urgent threshold that is due and has no row yet, so a reminder missed on its
    day (scheduler down, a failed run) goes out on the next run, and a second run never raises it again."""

    __tablename__ = "billing_trial_reminder"
    __table_args__ = (
        UniqueConstraint("organisation_id", "trial_ends_on", "threshold", name="uq_billing_trial_reminder"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    trial_ends_on: Mapped[str] = mapped_column(String(10))  # ISO date, UTC
    threshold: Mapped[int] = mapped_column(Integer)
    days_left: Mapped[int] = mapped_column(Integer)  # when it was raised: below the threshold if caught up
    raised_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
