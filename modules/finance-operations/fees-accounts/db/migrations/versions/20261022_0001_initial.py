"""Initial fees-accounts schema: fee heads and structures, invoices and their lines, payments, receipts, refunds,
concessions, the per-organisation number sequence, bulk jobs, collection targets and settings. Every table carries
organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: fees_accounts_0001
Revises:
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "fees_accounts_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "fees_accounts_fee_head",
    "fees_accounts_fee_structure",
    "fees_accounts_invoice",
    "fees_accounts_invoice_line",
    "fees_accounts_payment",
    "fees_accounts_receipt",
    "fees_accounts_refund",
    "fees_accounts_concession",
    "fees_accounts_number_sequence",
    "fees_accounts_bulk_job",
    "fees_accounts_collection_target",
    "fees_accounts_settings",
]
MONEY = sa.Numeric(12, 2)
NOT_CANCELLED = sa.text("status <> 'cancelled'")


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "fees_accounts_fee_head",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("refundable", sa.Boolean, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_fees_accounts_fee_head_code"),
    )
    _enable_rls("fees_accounts_fee_head")

    op.create_table(
        "fees_accounts_fee_structure",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("programme_id", sa.String(36), nullable=True),
        sa.Column("applies_to", sa.String(10), nullable=False),
        sa.Column("category", sa.String(60), nullable=True),
        sa.Column("room_type", sa.String(60), nullable=True),
        sa.Column("route_id", sa.String(36), nullable=True),
        sa.Column("items", sa.JSON, nullable=False),
        sa.Column("instalments", sa.JSON, nullable=False),
        sa.Column("allow_part_payment", sa.Boolean, nullable=False),
        sa.Column("late_fee", sa.JSON, nullable=True),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        _ts("published_at", nullable=True),
    )
    _enable_rls("fees_accounts_fee_structure")

    op.create_table(
        "fees_accounts_invoice",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("person_name", sa.String(200), nullable=True),
        sa.Column("fee_structure_id", sa.String(36), sa.ForeignKey("fees_accounts_fee_structure.id"), nullable=True),
        sa.Column("instalment", sa.Integer, nullable=True),
        sa.Column("academic_year", sa.String(9), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("concession_total", MONEY, nullable=False),
        sa.Column("late_fee", MONEY, nullable=False),
        sa.Column("paid_total", MONEY, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("allow_part_payment", sa.Boolean, nullable=False),
        sa.Column("late_fee_rule", sa.JSON, nullable=True),
        sa.Column("source_module", sa.String(60), nullable=True),
        sa.Column("source_reference", sa.String(100), nullable=True),
        _ts("issued_at"),
        sa.Column("issued_by", sa.String(36), nullable=True),
        _ts("paid_at", nullable=True),
        sa.Column("late_fee_updated_on", sa.Date, nullable=True),
        sa.Column("overdue_notified", sa.Boolean, nullable=False),
        _ts("cancelled_at", nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.UniqueConstraint("organisation_id", "number", name="uq_fees_accounts_invoice_number"),
    )
    _enable_rls("fees_accounts_invoice")

    op.create_table(
        "fees_accounts_invoice_line",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("fees_accounts_invoice.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("fee_head_id", sa.String(36), sa.ForeignKey("fees_accounts_fee_head.id"), nullable=False),
        sa.Column("fee_head_name", sa.String(120), nullable=False),
        sa.Column("description", sa.String(300), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
    )
    _enable_rls("fees_accounts_invoice_line")

    op.create_table(
        "fees_accounts_payment",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("fees_accounts_invoice.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("refunded_amount", MONEY, nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("gateway_reference", sa.String(40), nullable=True),
        sa.Column("instrument_number", sa.String(60), nullable=True),
        sa.Column("bank_name", sa.String(120), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("paid_on", sa.Date, nullable=False),
        sa.Column("receipt_id", sa.String(36), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=True),
        _ts("voided_at", nullable=True),
        sa.Column("void_reason", sa.Text, nullable=True),
        sa.UniqueConstraint("organisation_id", "gateway_reference", name="uq_fees_accounts_payment_gateway"),
    )
    _enable_rls("fees_accounts_payment")

    op.create_table(
        "fees_accounts_receipt",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("fees_accounts_payment.id"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("fees_accounts_invoice.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        _ts("issued_at"),
        sa.UniqueConstraint("organisation_id", "number", name="uq_fees_accounts_receipt_number"),
    )
    _enable_rls("fees_accounts_receipt")

    op.create_table(
        "fees_accounts_refund",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("payment_id", sa.String(36), sa.ForeignKey("fees_accounts_payment.id"), nullable=False),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("fees_accounts_invoice.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("mode", sa.String(20), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("gateway_refund_id", sa.String(100), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        _ts("completed_at", nullable=True),
    )
    _enable_rls("fees_accounts_refund")

    op.create_table(
        "fees_accounts_concession",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("invoice_id", sa.String(36), sa.ForeignKey("fees_accounts_invoice.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("amount", MONEY, nullable=True),
        sa.Column("percent", sa.Numeric(5, 2), nullable=True),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("approved_amount", MONEY, nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
    )
    _enable_rls("fees_accounts_concession")

    op.create_table(
        "fees_accounts_number_sequence",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("last_value", sa.Integer, nullable=False),
        sa.UniqueConstraint("organisation_id", "kind", name="uq_fees_accounts_number_sequence"),
    )
    _enable_rls("fees_accounts_number_sequence")

    op.create_table(
        "fees_accounts_bulk_job",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("fee_structure_id", sa.String(36), nullable=False),
        sa.Column("instalment", sa.Integer, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("requested", sa.Integer, nullable=False),
        sa.Column("created", sa.Integer, nullable=False),
        sa.Column("skipped", sa.Integer, nullable=False),
        sa.Column("errors", sa.JSON, nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=True),
    )
    _enable_rls("fees_accounts_bulk_job")

    op.create_table(
        "fees_accounts_collection_target",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("academic_year", sa.String(9), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("fee_head_id", sa.String(36), nullable=True),
        sa.Column("amount", MONEY, nullable=False),
    )
    _enable_rls("fees_accounts_collection_target")

    op.create_table(
        "fees_accounts_settings",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("invoice_library_fines", sa.Boolean, nullable=False),
        sa.Column("invoice_staff_transport", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", name="uq_fees_accounts_settings_org"),
    )
    _enable_rls("fees_accounts_settings")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_fees_accounts_fee_structure_academic_year", "fees_accounts_fee_structure", ["academic_year"])
    op.create_index("ix_fees_accounts_invoice_person_id", "fees_accounts_invoice", ["person_id"])
    op.create_index("ix_fees_accounts_invoice_status", "fees_accounts_invoice", ["status"])
    op.create_index("ix_fees_accounts_invoice_due_date", "fees_accounts_invoice", ["due_date"])
    # One live invoice per person, structure and instalment (see Invoice.__table_args__).
    op.create_index(
        "uq_fees_accounts_invoice_instalment",
        "fees_accounts_invoice",
        ["organisation_id", "person_id", "fee_structure_id", "instalment"],
        unique=True,
        sqlite_where=NOT_CANCELLED,
        postgresql_where=NOT_CANCELLED,
    )
    op.create_index("ix_fees_accounts_invoice_line_invoice_id", "fees_accounts_invoice_line", ["invoice_id"])
    op.create_index("ix_fees_accounts_payment_invoice_id", "fees_accounts_payment", ["invoice_id"])
    op.create_index("ix_fees_accounts_payment_person_id", "fees_accounts_payment", ["person_id"])
    op.create_index("ix_fees_accounts_payment_paid_on", "fees_accounts_payment", ["paid_on"])
    op.create_index("ix_fees_accounts_receipt_payment_id", "fees_accounts_receipt", ["payment_id"])
    op.create_index("ix_fees_accounts_receipt_person_id", "fees_accounts_receipt", ["person_id"])
    op.create_index("ix_fees_accounts_refund_payment_id", "fees_accounts_refund", ["payment_id"])
    op.create_index("ix_fees_accounts_concession_invoice_id", "fees_accounts_concession", ["invoice_id"])
    op.create_index("ix_fees_accounts_concession_person_id", "fees_accounts_concession", ["person_id"])
    op.create_index("ix_fees_accounts_concession_status", "fees_accounts_concession", ["status"])
    op.create_index(
        "ix_fees_accounts_collection_target_academic_year", "fees_accounts_collection_target", ["academic_year"]
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
