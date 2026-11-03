"""Tables of hr-payroll. One shared schema with the hr_payroll_ prefix; every table carries organisation_id
(TenantMixin) and gets the tenant_isolation row-level-security policy on Postgres. Money is Numeric(14, 2) and leave
days Numeric(5, 1). Nothing is deleted: employees exit, leave is rejected or cancelled, salary structures are kept
when a new one takes effect, and payroll runs are locked once approved. Pay lines are JSON on their structure or
payslip, with amounts as decimal strings.

Bank account numbers and PANs are never stored in full: only the last four digits of the account with its IFSC, and
the last four characters of the PAN (decided by the owner; see #336)."""

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
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "hr_payroll_"
MONEY = Numeric(14, 2)
DAYS = Numeric(5, 1)


class Employee(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}employee"
    __table_args__ = (
        UniqueConstraint("organisation_id", "employee_code", name="uq_hr_payroll_employee_code"),
        UniqueConstraint("organisation_id", "user_id", name="uq_hr_payroll_employee_user"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    employee_code: Mapped[str] = mapped_column(String(40))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # platform/identity user, never a key
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(254), default="")
    phone: Mapped[str] = mapped_column(String(40), default="")
    date_of_birth: Mapped[date | None] = mapped_column(Date, nullable=True)
    joined_on: Mapped[date] = mapped_column(Date)
    employment_type: Mapped[str] = mapped_column(String(12))
    staff_category: Mapped[str | None] = mapped_column(String(12), nullable=True)
    designation: Mapped[str] = mapped_column(String(120), default="")
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    department_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    reports_to: Mapped[str | None] = mapped_column(String(36), nullable=True)  # another employee of the organisation
    bank_account_holder: Mapped[str | None] = mapped_column(String(200), nullable=True)
    bank_account_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    bank_ifsc: Mapped[str | None] = mapped_column(String(11), nullable=True)
    pan_last4: Mapped[str | None] = mapped_column(String(4), nullable=True)
    status: Mapped[str] = mapped_column(String(10), default="active", index=True)
    exit_kind: Mapped[str | None] = mapped_column(String(14), nullable=True)
    exit_last_working_day: Mapped[date | None] = mapped_column(Date, nullable=True)
    exit_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    exit_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SalaryStructure(Base, TenantMixin, TimestampMixin):
    """An employee's pay lines from an effective date. A later structure replaces it from its own date."""

    __tablename__ = f"{PREFIX}salary_structure"
    __table_args__ = (UniqueConstraint("employee_id", "effective_from", name="uq_hr_payroll_salary_effective"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}employee.id"), index=True)
    effective_from: Mapped[date] = mapped_column(Date)
    lines: Mapped[list] = mapped_column(JSON)
    gross: Mapped[Decimal] = mapped_column(MONEY)
    deductions: Mapped[Decimal] = mapped_column(MONEY)
    net: Mapped[Decimal] = mapped_column(MONEY)
    set_by: Mapped[str] = mapped_column(String(36))


class ServiceRecord(Base, TenantMixin, TimestampMixin):
    """One entry of the service book. `document_id` stays empty until the documents SDK exists."""

    __tablename__ = f"{PREFIX}service_record"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}employee.id"), index=True)
    kind: Mapped[str] = mapped_column(String(14))
    effective_on: Mapped[date] = mapped_column(Date)
    title: Mapped[str] = mapped_column(String(300))
    details: Mapped[str] = mapped_column(Text, default="")
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    recorded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)


class LeaveType(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}leave_type"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_hr_payroll_leave_type_code"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(20))
    name: Mapped[str] = mapped_column(String(120))
    days_per_year: Mapped[Decimal] = mapped_column(DAYS)
    carry_forward_max: Mapped[Decimal] = mapped_column(DAYS)
    paid: Mapped[bool] = mapped_column(Boolean, default=True)
    half_day_allowed: Mapped[bool] = mapped_column(Boolean, default=True)
    applies_to: Mapped[list] = mapped_column(JSON)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class LeaveRequest(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}leave_request"
    __table_args__ = (Index("ix_hr_payroll_leave_request_employee_dates", "employee_id", "from_date", "to_date"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}employee.id"), index=True)
    leave_type_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}leave_type.id"), index=True)
    from_date: Mapped[date] = mapped_column(Date)
    to_date: Mapped[date] = mapped_column(Date)
    half_day: Mapped[str] = mapped_column(String(12), default="none")
    days: Mapped[Decimal] = mapped_column(DAYS)
    paid: Mapped[bool] = mapped_column(Boolean)  # the leave type's at the time of applying; unpaid is loss of pay
    reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(10), default="pending", index=True)
    approver_id: Mapped[str | None] = mapped_column(String(36), nullable=True)  # the reporting manager's user
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)


class PayrollRun(Base, TenantMixin, TimestampMixin):
    """One month's payroll. `preparers` lists everyone who started, adjusted or submitted it: none of them approves."""

    __tablename__ = f"{PREFIX}payroll_run"
    __table_args__ = (UniqueConstraint("organisation_id", "period", name="uq_hr_payroll_payroll_run_period"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    period: Mapped[str] = mapped_column(String(7))
    status: Mapped[str] = mapped_column(String(10), default="computing", index=True)
    employees: Mapped[int] = mapped_column(Integer, default=0)
    gross_total: Mapped[Decimal] = mapped_column(MONEY)
    deductions_total: Mapped[Decimal] = mapped_column(MONEY)
    net_total: Mapped[Decimal] = mapped_column(MONEY)
    exceptions: Mapped[list] = mapped_column(JSON)
    prepared_by: Mapped[str] = mapped_column(String(36))
    preparers: Mapped[list] = mapped_column(JSON)
    approved_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    paid_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    bank_reference: Mapped[str | None] = mapped_column(String(120), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Payslip(Base, TenantMixin, TimestampMixin):
    """One employee's pay for a run. `adjustments` keeps every change HR made, with its reason."""

    __tablename__ = f"{PREFIX}payslip"
    __table_args__ = (UniqueConstraint("run_id", "employee_id", name="uq_hr_payroll_payslip_employee"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    run_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}payroll_run.id"), index=True)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}employee.id"), index=True)
    employee_name: Mapped[str] = mapped_column(String(200))
    period: Mapped[str] = mapped_column(String(7))
    days_in_month: Mapped[int] = mapped_column(Integer)
    paid_days: Mapped[Decimal] = mapped_column(DAYS)
    loss_of_pay_days: Mapped[Decimal] = mapped_column(DAYS)
    lines: Mapped[list] = mapped_column(JSON)
    gross: Mapped[Decimal] = mapped_column(MONEY)
    deductions: Mapped[Decimal] = mapped_column(MONEY)
    net: Mapped[Decimal] = mapped_column(MONEY)
    adjustments: Mapped[list] = mapped_column(JSON)
    document_id: Mapped[str | None] = mapped_column(String(100), nullable=True)


class Appraisal(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}appraisal"
    __table_args__ = (UniqueConstraint("employee_id", "cycle", name="uq_hr_payroll_appraisal_cycle"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    cycle: Mapped[str] = mapped_column(String(20), index=True)
    employee_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}employee.id"), index=True)
    status: Mapped[str] = mapped_column(String(14), default="self_review", index=True)
    self_review: Mapped[str] = mapped_column(Text, default="")
    reviewer_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    reviewer_comments: Mapped[str] = mapped_column(Text, default="")
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    opened_by: Mapped[str] = mapped_column(String(36))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only, never amounts, account numbers or PANs. Stands in for the audit SDK until it
    ships, as in procurement, budget-grants and fees-accounts."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_hr_payroll_audit_entity", "organisation_id", "entity", "entity_id"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [
    m.__table__
    for m in (
        Employee,
        SalaryStructure,
        ServiceRecord,
        LeaveType,
        LeaveRequest,
        PayrollRun,
        Payslip,
        Appraisal,
        AuditEntry,
    )
]
