from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import JSON, Boolean, DateTime, Integer, Numeric, String
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

    def to_dict(self) -> dict:
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
        }
