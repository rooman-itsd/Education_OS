"""Tables of budget-grants. One shared schema with the budget_grants_ prefix; every table carries organisation_id
(TenantMixin) and gets the tenant_isolation row-level-security policy on Postgres. Money is Numeric(14, 2).
Nothing is deleted: expenditure is reversed with a reason, approved budgets change only by reappropriation."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import JSON, Boolean, Date, DateTime, ForeignKey, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "budget_grants_"
MONEY = Numeric(14, 2)


class BudgetHead(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}budget_head"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_budget_grants_budget_head_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    kind: Mapped[str] = mapped_column(String(20), default="recurring")
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Budget(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}budget"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    financial_year: Mapped[str] = mapped_column(String(7), index=True)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    title: Mapped[str] = mapped_column(String(200), default="")
    status: Mapped[str] = mapped_column(String(10), default="draft", index=True)
    prepared_by: Mapped[str] = mapped_column(String(36))
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Grant(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}grant"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_budget_grants_grant_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(300))
    funder: Mapped[str] = mapped_column(String(200))
    scheme: Mapped[str] = mapped_column(String(200), default="")
    sanction_order_document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sanctioned_amount: Mapped[Decimal] = mapped_column(MONEY)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    uc_frequency: Mapped[str] = mapped_column(String(15), default="yearly")
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)
    unspent_action: Mapped[str | None] = mapped_column(String(15), nullable=True)
    close_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Line(Base, TenantMixin):
    """A budget line or a grant line: an allocation for one budget head that commitments and spend are charged to."""

    __tablename__ = f"{PREFIX}line"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(10))  # budget | grant
    budget_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}budget.id"), nullable=True, index=True
    )
    grant_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}grant.id"), nullable=True, index=True)
    budget_head_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}budget_head.id"))
    allocated: Mapped[Decimal] = mapped_column(MONEY)
    note: Mapped[str] = mapped_column(Text, default="")


class Expenditure(Base, TenantMixin):
    """A commitment or actual spend on a line. A release of a commitment is a negative commitment. Entries from
    other modules are unique by source, so a repeated event records nothing."""

    __tablename__ = f"{PREFIX}expenditure"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "source_module", "source_reference", "kind", name="uq_budget_grants_expenditure_source"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    line_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}line.id"), index=True)
    kind: Mapped[str] = mapped_column(String(10))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    date: Mapped[date] = mapped_column(Date, index=True)
    description: Mapped[str] = mapped_column(String(300))
    source_module: Mapped[str] = mapped_column(String(30), default="manual")
    source_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    purchase_order_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reversed: Mapped[bool] = mapped_column(Boolean, default=False)
    reversal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Reappropriation(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}reappropriation"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    from_line_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}line.id"))
    to_line_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}line.id"))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(10), default="requested", index=True)
    requested_by: Mapped[str] = mapped_column(String(36))
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)


class Investigator(Base, TenantMixin):
    __tablename__ = f"{PREFIX}investigator"
    __table_args__ = (UniqueConstraint("grant_id", "user_id", name="uq_budget_grants_investigator"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grant_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}grant.id"), index=True)
    user_id: Mapped[str] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(20))


class FundsReceived(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}funds_received"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grant_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}grant.id"), index=True)
    amount: Mapped[Decimal] = mapped_column(MONEY)
    received_on: Mapped[date] = mapped_column(Date)
    reference: Mapped[str | None] = mapped_column(String(120), nullable=True)


class UtilisationCertificate(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}utilisation_certificate"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grant_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}grant.id"), index=True)
    period_from: Mapped[date] = mapped_column(Date)
    period_to: Mapped[date] = mapped_column(Date)
    opening_balance: Mapped[Decimal] = mapped_column(MONEY)
    received: Mapped[Decimal] = mapped_column(MONEY)
    spent: Mapped[Decimal] = mapped_column(MONEY)
    closing_balance: Mapped[Decimal] = mapped_column(MONEY)
    by_head: Mapped[list] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(String(10), default="draft")
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    prepared_by: Mapped[str] = mapped_column(String(36))
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decision_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    submission_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)


class Alert(Base, TenantMixin):
    """A notice already published, so the daily sweep and spend never repeat it: a line crossing a threshold, or a
    certificate reminder for one due date and day count."""

    __tablename__ = f"{PREFIX}alert"
    __table_args__ = (UniqueConstraint("organisation_id", "kind", "subject_id", "key", name="uq_budget_grants_alert"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    kind: Mapped[str] = mapped_column(String(20))  # threshold | uc_due
    subject_id: Mapped[str] = mapped_column(String(36))
    key: Mapped[str] = mapped_column(String(40))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [
    m.__table__
    for m in (
        BudgetHead,
        Budget,
        Grant,
        Line,
        Expenditure,
        Reappropriation,
        Investigator,
        FundsReceived,
        UtilisationCertificate,
        Alert,
    )
]
