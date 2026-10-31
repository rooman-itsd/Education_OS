"""Initial hr-payroll schema: employees, salary structures, the service book, leave types and requests, payroll runs
and their payslips, appraisals and the audit trail. Every table carries organisation_id; on Postgres each gets the
tenant_isolation row-level-security policy. Bank accounts and PANs keep their last four characters only (#336).

Revision ID: hr_payroll_0001
Revises:
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "hr_payroll_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "hr_payroll_employee",
    "hr_payroll_salary_structure",
    "hr_payroll_service_record",
    "hr_payroll_leave_type",
    "hr_payroll_leave_request",
    "hr_payroll_payroll_run",
    "hr_payroll_payslip",
    "hr_payroll_appraisal",
    "hr_payroll_audit_entry",
]
MONEY = sa.Numeric(14, 2)
DAYS = sa.Numeric(5, 1)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "hr_payroll_employee",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("employee_code", sa.String(40), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("joined_on", sa.Date, nullable=False),
        sa.Column("employment_type", sa.String(12), nullable=False),
        sa.Column("staff_category", sa.String(12), nullable=True),
        sa.Column("designation", sa.String(120), nullable=False),
        sa.Column("department_id", sa.String(36), nullable=True),
        sa.Column("department_name", sa.String(200), nullable=True),
        sa.Column("reports_to", sa.String(36), nullable=True),
        sa.Column("bank_account_holder", sa.String(200), nullable=True),
        sa.Column("bank_account_last4", sa.String(4), nullable=True),
        sa.Column("bank_ifsc", sa.String(11), nullable=True),
        sa.Column("pan_last4", sa.String(4), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("exit_kind", sa.String(14), nullable=True),
        sa.Column("exit_last_working_day", sa.Date, nullable=True),
        sa.Column("exit_reason", sa.Text, nullable=True),
        _ts("exit_published_at", nullable=True),
        sa.UniqueConstraint("organisation_id", "employee_code", name="uq_hr_payroll_employee_code"),
        sa.UniqueConstraint("organisation_id", "user_id", name="uq_hr_payroll_employee_user"),
    )
    _enable_rls("hr_payroll_employee")

    op.create_table(
        "hr_payroll_salary_structure",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_payroll_employee.id"), nullable=False),
        sa.Column("effective_from", sa.Date, nullable=False),
        sa.Column("lines", sa.JSON, nullable=False),
        sa.Column("gross", MONEY, nullable=False),
        sa.Column("deductions", MONEY, nullable=False),
        sa.Column("net", MONEY, nullable=False),
        sa.Column("set_by", sa.String(36), nullable=False),
        sa.UniqueConstraint("employee_id", "effective_from", name="uq_hr_payroll_salary_effective"),
    )
    _enable_rls("hr_payroll_salary_structure")

    op.create_table(
        "hr_payroll_service_record",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_payroll_employee.id"), nullable=False),
        sa.Column("kind", sa.String(14), nullable=False),
        sa.Column("effective_on", sa.Date, nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("details", sa.Text, nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
    )
    _enable_rls("hr_payroll_service_record")

    op.create_table(
        "hr_payroll_leave_type",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("days_per_year", DAYS, nullable=False),
        sa.Column("carry_forward_max", DAYS, nullable=False),
        sa.Column("paid", sa.Boolean, nullable=False),
        sa.Column("half_day_allowed", sa.Boolean, nullable=False),
        sa.Column("applies_to", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_hr_payroll_leave_type_code"),
    )
    _enable_rls("hr_payroll_leave_type")

    op.create_table(
        "hr_payroll_leave_request",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_payroll_employee.id"), nullable=False),
        sa.Column("leave_type_id", sa.String(36), sa.ForeignKey("hr_payroll_leave_type.id"), nullable=False),
        sa.Column("from_date", sa.Date, nullable=False),
        sa.Column("to_date", sa.Date, nullable=False),
        sa.Column("half_day", sa.String(12), nullable=False),
        sa.Column("days", DAYS, nullable=False),
        sa.Column("paid", sa.Boolean, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("approver_id", sa.String(36), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        sa.Column("note", sa.Text, nullable=True),
    )
    _enable_rls("hr_payroll_leave_request")

    op.create_table(
        "hr_payroll_payroll_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("employees", sa.Integer, nullable=False),
        sa.Column("gross_total", MONEY, nullable=False),
        sa.Column("deductions_total", MONEY, nullable=False),
        sa.Column("net_total", MONEY, nullable=False),
        sa.Column("exceptions", sa.JSON, nullable=False),
        sa.Column("prepared_by", sa.String(36), nullable=False),
        sa.Column("preparers", sa.JSON, nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        _ts("submitted_at", nullable=True),
        _ts("approved_at", nullable=True),
        sa.Column("paid_on", sa.Date, nullable=True),
        sa.Column("bank_reference", sa.String(120), nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "period", name="uq_hr_payroll_payroll_run_period"),
    )
    _enable_rls("hr_payroll_payroll_run")

    op.create_table(
        "hr_payroll_payslip",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("hr_payroll_payroll_run.id"), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_payroll_employee.id"), nullable=False),
        sa.Column("employee_name", sa.String(200), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("days_in_month", sa.Integer, nullable=False),
        sa.Column("paid_days", DAYS, nullable=False),
        sa.Column("loss_of_pay_days", DAYS, nullable=False),
        sa.Column("lines", sa.JSON, nullable=False),
        sa.Column("gross", MONEY, nullable=False),
        sa.Column("deductions", MONEY, nullable=False),
        sa.Column("net", MONEY, nullable=False),
        sa.Column("adjustments", sa.JSON, nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.UniqueConstraint("run_id", "employee_id", name="uq_hr_payroll_payslip_employee"),
    )
    _enable_rls("hr_payroll_payslip")

    op.create_table(
        "hr_payroll_appraisal",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("cycle", sa.String(20), nullable=False),
        sa.Column("employee_id", sa.String(36), sa.ForeignKey("hr_payroll_employee.id"), nullable=False),
        sa.Column("status", sa.String(14), nullable=False),
        sa.Column("self_review", sa.Text, nullable=False),
        sa.Column("reviewer_id", sa.String(36), nullable=True),
        sa.Column("reviewer_comments", sa.Text, nullable=False),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("opened_by", sa.String(36), nullable=False),
        _ts("completed_at", nullable=True),
        sa.UniqueConstraint("employee_id", "cycle", name="uq_hr_payroll_appraisal_cycle"),
    )
    _enable_rls("hr_payroll_appraisal")

    op.create_table(
        "hr_payroll_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )
    _enable_rls("hr_payroll_audit_entry")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_hr_payroll_employee_status", "hr_payroll_employee", ["status"])
    op.create_index("ix_hr_payroll_salary_structure_employee_id", "hr_payroll_salary_structure", ["employee_id"])
    op.create_index("ix_hr_payroll_service_record_employee_id", "hr_payroll_service_record", ["employee_id"])
    op.create_index("ix_hr_payroll_leave_request_employee_id", "hr_payroll_leave_request", ["employee_id"])
    op.create_index("ix_hr_payroll_leave_request_leave_type_id", "hr_payroll_leave_request", ["leave_type_id"])
    op.create_index("ix_hr_payroll_leave_request_status", "hr_payroll_leave_request", ["status"])
    op.create_index(
        "ix_hr_payroll_leave_request_employee_dates",
        "hr_payroll_leave_request",
        ["employee_id", "from_date", "to_date"],
    )
    op.create_index("ix_hr_payroll_payroll_run_status", "hr_payroll_payroll_run", ["status"])
    op.create_index("ix_hr_payroll_payslip_run_id", "hr_payroll_payslip", ["run_id"])
    op.create_index("ix_hr_payroll_payslip_employee_id", "hr_payroll_payslip", ["employee_id"])
    op.create_index("ix_hr_payroll_appraisal_cycle", "hr_payroll_appraisal", ["cycle"])
    op.create_index("ix_hr_payroll_appraisal_employee_id", "hr_payroll_appraisal", ["employee_id"])
    op.create_index("ix_hr_payroll_appraisal_status", "hr_payroll_appraisal", ["status"])
    op.create_index("ix_hr_payroll_audit_entity", "hr_payroll_audit_entry", ["organisation_id", "entity", "entity_id"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
