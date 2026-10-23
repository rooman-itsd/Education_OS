"""Initial budget-grants schema: budget heads, budgets, grants, their lines, commitments and spend, reappropriations,
investigators, funds received, utilisation certificates and published alerts and the audit trail. Every table carries organisation_id;
on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: budget_grants_0001
Revises:
Create Date: 2026-10-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "budget_grants_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "budget_grants_budget_head",
    "budget_grants_budget",
    "budget_grants_grant",
    "budget_grants_line",
    "budget_grants_expenditure",
    "budget_grants_reappropriation",
    "budget_grants_investigator",
    "budget_grants_funds_received",
    "budget_grants_utilisation_certificate",
    "budget_grants_alert",
    "budget_grants_audit_entry",
]
MONEY = sa.Numeric(14, 2)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "budget_grants_budget_head",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_budget_grants_budget_head_code"),
    )
    _enable_rls("budget_grants_budget_head")

    op.create_table(
        "budget_grants_budget",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("financial_year", sa.String(7), nullable=False),
        sa.Column("department_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("prepared_by", sa.String(36), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        _ts("approved_at", nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
    )
    _enable_rls("budget_grants_budget")

    op.create_table(
        "budget_grants_grant",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("funder", sa.String(200), nullable=False),
        sa.Column("scheme", sa.String(200), nullable=False),
        sa.Column("sanction_order_document_id", sa.String(100), nullable=True),
        sa.Column("sanctioned_amount", MONEY, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("department_id", sa.String(36), nullable=True),
        sa.Column("uc_frequency", sa.String(15), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("unspent_action", sa.String(15), nullable=True),
        sa.Column("close_note", sa.Text, nullable=True),
        _ts("closed_at", nullable=True),
        sa.UniqueConstraint("organisation_id", "code", name="uq_budget_grants_grant_code"),
    )
    _enable_rls("budget_grants_grant")

    op.create_table(
        "budget_grants_line",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("budget_id", sa.String(36), sa.ForeignKey("budget_grants_budget.id"), nullable=True),
        sa.Column("grant_id", sa.String(36), sa.ForeignKey("budget_grants_grant.id"), nullable=True),
        sa.Column("budget_head_id", sa.String(36), sa.ForeignKey("budget_grants_budget_head.id"), nullable=False),
        sa.Column("allocated", MONEY, nullable=False),
        sa.Column("note", sa.Text, nullable=False),
    )
    _enable_rls("budget_grants_line")

    op.create_table(
        "budget_grants_expenditure",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("line_id", sa.String(36), sa.ForeignKey("budget_grants_line.id"), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("source_module", sa.String(30), nullable=False),
        sa.Column("source_reference", sa.String(120), nullable=True),
        sa.Column("purchase_order_id", sa.String(36), nullable=True),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("reversed", sa.Boolean, nullable=False),
        sa.Column("reversal_reason", sa.Text, nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        _ts("recorded_at"),
        sa.UniqueConstraint(
            "organisation_id", "source_module", "source_reference", "kind", name="uq_budget_grants_expenditure_source"
        ),
    )
    _enable_rls("budget_grants_expenditure")

    op.create_table(
        "budget_grants_reappropriation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("from_line_id", sa.String(36), sa.ForeignKey("budget_grants_line.id"), nullable=False),
        sa.Column("to_line_id", sa.String(36), sa.ForeignKey("budget_grants_line.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
    )
    _enable_rls("budget_grants_reappropriation")

    op.create_table(
        "budget_grants_investigator",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("grant_id", sa.String(36), sa.ForeignKey("budget_grants_grant.id"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.UniqueConstraint("grant_id", "user_id", name="uq_budget_grants_investigator"),
    )
    _enable_rls("budget_grants_investigator")

    op.create_table(
        "budget_grants_funds_received",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("grant_id", sa.String(36), sa.ForeignKey("budget_grants_grant.id"), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("received_on", sa.Date, nullable=False),
        sa.Column("reference", sa.String(120), nullable=True),
    )
    _enable_rls("budget_grants_funds_received")

    op.create_table(
        "budget_grants_utilisation_certificate",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("grant_id", sa.String(36), sa.ForeignKey("budget_grants_grant.id"), nullable=False),
        sa.Column("period_from", sa.Date, nullable=False),
        sa.Column("period_to", sa.Date, nullable=False),
        sa.Column("opening_balance", MONEY, nullable=False),
        sa.Column("received", MONEY, nullable=False),
        sa.Column("spent", MONEY, nullable=False),
        sa.Column("closing_balance", MONEY, nullable=False),
        sa.Column("by_head", sa.JSON, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("prepared_by", sa.String(36), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("submitted_on", sa.Date, nullable=True),
        sa.Column("submission_reference", sa.String(120), nullable=True),
    )
    _enable_rls("budget_grants_utilisation_certificate")

    op.create_table(
        "budget_grants_alert",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("subject_id", sa.String(36), nullable=False),
        sa.Column("key", sa.String(40), nullable=False),
        _ts("sent_at"),
        sa.UniqueConstraint("organisation_id", "kind", "subject_id", "key", name="uq_budget_grants_alert"),
    )
    _enable_rls("budget_grants_alert")

    op.create_table(
        "budget_grants_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )
    _enable_rls("budget_grants_audit_entry")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_budget_grants_budget_financial_year", "budget_grants_budget", ["financial_year"])
    op.create_index("ix_budget_grants_budget_status", "budget_grants_budget", ["status"])
    op.create_index("ix_budget_grants_grant_status", "budget_grants_grant", ["status"])
    op.create_index("ix_budget_grants_line_budget_id", "budget_grants_line", ["budget_id"])
    op.create_index("ix_budget_grants_line_grant_id", "budget_grants_line", ["grant_id"])
    op.create_index("ix_budget_grants_expenditure_line_id", "budget_grants_expenditure", ["line_id"])
    op.create_index("ix_budget_grants_expenditure_date", "budget_grants_expenditure", ["date"])
    op.create_index(
        "ix_budget_grants_expenditure_purchase_order_id", "budget_grants_expenditure", ["purchase_order_id"]
    )
    op.create_index("ix_budget_grants_reappropriation_status", "budget_grants_reappropriation", ["status"])
    op.create_index("ix_budget_grants_investigator_grant_id", "budget_grants_investigator", ["grant_id"])
    op.create_index("ix_budget_grants_investigator_user_id", "budget_grants_investigator", ["user_id"])
    op.create_index("ix_budget_grants_funds_received_grant_id", "budget_grants_funds_received", ["grant_id"])
    op.create_index(
        "ix_budget_grants_utilisation_certificate_grant_id", "budget_grants_utilisation_certificate", ["grant_id"]
    )
    op.create_index(
        "ix_budget_grants_audit_entity", "budget_grants_audit_entry", ["organisation_id", "entity", "entity_id"]
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
