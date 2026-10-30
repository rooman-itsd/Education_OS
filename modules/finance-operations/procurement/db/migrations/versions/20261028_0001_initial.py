"""Initial procurement schema: vendors, indents, tenders and their quotes, purchase orders, the indents each tender and
order buys for, goods receipts, vendor invoices and the audit trail. Every table carries organisation_id; on Postgres
each gets the tenant_isolation row-level-security policy.

Revision ID: procurement_0001
Revises:
Create Date: 2026-10-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "procurement_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "procurement_vendor",
    "procurement_indent",
    "procurement_tender",
    "procurement_quote",
    "procurement_purchase_order",
    "procurement_tender_indent",
    "procurement_order_indent",
    "procurement_goods_receipt",
    "procurement_vendor_invoice",
    "procurement_audit_entry",
]
MONEY = sa.Numeric(14, 2)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "procurement_vendor",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("categories", sa.JSON, nullable=False),
        sa.Column("contact_name", sa.String(200), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("phone", sa.String(40), nullable=False),
        sa.Column("address", sa.Text, nullable=False),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("pan", sa.String(10), nullable=True),
        sa.Column("msme_registration", sa.String(40), nullable=True),
        sa.Column("bank_account_last4", sa.String(4), nullable=True),
        sa.Column("bank_ifsc", sa.String(11), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("status_reason", sa.Text, nullable=True),
        sa.UniqueConstraint("organisation_id", "gstin", name="uq_procurement_vendor_gstin"),
        sa.UniqueConstraint("organisation_id", "pan", name="uq_procurement_vendor_pan"),
    )
    _enable_rls("procurement_vendor")

    op.create_table(
        "procurement_indent",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("department_id", sa.String(36), nullable=True),
        sa.Column("line_id", sa.String(36), nullable=False),
        sa.Column("items", sa.JSON, nullable=False),
        sa.Column("estimated_cost", MONEY, nullable=False),
        sa.Column("needed_by", sa.Date, nullable=True),
        sa.Column("document_ids", sa.JSON, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("purchase_method", sa.String(10), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.UniqueConstraint("organisation_id", "number", name="uq_procurement_indent_number"),
    )
    _enable_rls("procurement_indent")

    op.create_table(
        "procurement_tender",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("method", sa.String(10), nullable=False),
        sa.Column("line_id", sa.String(36), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("invited_vendor_ids", sa.JSON, nullable=False),
        _ts("closes_at"),
        sa.Column("terms", sa.Text, nullable=False),
        sa.Column("document_ids", sa.JSON, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("awarded_quote_id", sa.String(36), nullable=True),
        sa.Column("award_justification", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.UniqueConstraint("organisation_id", "number", name="uq_procurement_tender_number"),
    )
    _enable_rls("procurement_tender")

    op.create_table(
        "procurement_quote",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("tender_id", sa.String(36), sa.ForeignKey("procurement_tender.id"), nullable=False),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("procurement_vendor.id"), nullable=False),
        sa.Column("items", sa.JSON, nullable=False),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("delivery_days", sa.Integer, nullable=True),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
        sa.UniqueConstraint("tender_id", "vendor_id", name="uq_procurement_quote_vendor"),
    )
    _enable_rls("procurement_quote")

    op.create_table(
        "procurement_purchase_order",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("procurement_vendor.id"), nullable=False),
        sa.Column("tender_id", sa.String(36), sa.ForeignKey("procurement_tender.id"), nullable=True),
        sa.Column("line_id", sa.String(36), nullable=False),
        sa.Column("items", sa.JSON, nullable=False),
        sa.Column("delivery_by", sa.Date, nullable=False),
        sa.Column("delivery_address", sa.Text, nullable=False),
        sa.Column("terms", sa.Text, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("subtotal", MONEY, nullable=False),
        sa.Column("tax_total", MONEY, nullable=False),
        sa.Column("total", MONEY, nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("prepared_by", sa.String(36), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        _ts("submitted_at", nullable=True),
        _ts("issued_at", nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.UniqueConstraint("organisation_id", "number", name="uq_procurement_purchase_order_number"),
    )
    _enable_rls("procurement_purchase_order")

    op.create_table(
        "procurement_tender_indent",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("tender_id", sa.String(36), sa.ForeignKey("procurement_tender.id"), nullable=False),
        sa.Column("indent_id", sa.String(36), sa.ForeignKey("procurement_indent.id"), nullable=False),
        sa.UniqueConstraint("tender_id", "indent_id", name="uq_procurement_tender_indent"),
    )
    _enable_rls("procurement_tender_indent")

    op.create_table(
        "procurement_order_indent",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("procurement_purchase_order.id"), nullable=False),
        sa.Column("indent_id", sa.String(36), sa.ForeignKey("procurement_indent.id"), nullable=False),
        sa.UniqueConstraint("purchase_order_id", "indent_id", name="uq_procurement_order_indent"),
    )
    _enable_rls("procurement_order_indent")

    op.create_table(
        "procurement_goods_receipt",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("procurement_purchase_order.id"), nullable=False),
        sa.Column("received_on", sa.Date, nullable=False),
        sa.Column("delivery_note", sa.Text, nullable=False),
        sa.Column("items", sa.JSON, nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
        sa.UniqueConstraint("organisation_id", "number", name="uq_procurement_goods_receipt_number"),
    )
    _enable_rls("procurement_goods_receipt")

    op.create_table(
        "procurement_vendor_invoice",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("purchase_order_id", sa.String(36), sa.ForeignKey("procurement_purchase_order.id"), nullable=False),
        sa.Column("vendor_id", sa.String(36), sa.ForeignKey("procurement_vendor.id"), nullable=False),
        sa.Column("invoice_number", sa.String(60), nullable=False),
        sa.Column("invoice_date", sa.Date, nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("tax_amount", MONEY, nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("recorded_by", sa.String(36), nullable=False),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("paid_on", sa.Date, nullable=True),
        sa.Column("payment_reference", sa.String(120), nullable=True),
        sa.Column("tds_deducted", MONEY, nullable=False),
        sa.UniqueConstraint(
            "organisation_id", "vendor_id", "invoice_number", name="uq_procurement_vendor_invoice_number"
        ),
    )
    _enable_rls("procurement_vendor_invoice")

    op.create_table(
        "procurement_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )
    _enable_rls("procurement_audit_entry")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_procurement_vendor_status", "procurement_vendor", ["status"])
    op.create_index("ix_procurement_indent_line_id", "procurement_indent", ["line_id"])
    op.create_index("ix_procurement_indent_status", "procurement_indent", ["status"])
    op.create_index("ix_procurement_indent_requested_by", "procurement_indent", ["requested_by"])
    op.create_index("ix_procurement_tender_status", "procurement_tender", ["status"])
    op.create_index("ix_procurement_quote_tender_id", "procurement_quote", ["tender_id"])
    op.create_index("ix_procurement_purchase_order_vendor_id", "procurement_purchase_order", ["vendor_id"])
    op.create_index("ix_procurement_purchase_order_status", "procurement_purchase_order", ["status"])
    op.create_index("ix_procurement_tender_indent_tender_id", "procurement_tender_indent", ["tender_id"])
    op.create_index("ix_procurement_tender_indent_indent_id", "procurement_tender_indent", ["indent_id"])
    op.create_index("ix_procurement_order_indent_purchase_order_id", "procurement_order_indent", ["purchase_order_id"])
    op.create_index("ix_procurement_order_indent_indent_id", "procurement_order_indent", ["indent_id"])
    op.create_index(
        "ix_procurement_goods_receipt_purchase_order_id", "procurement_goods_receipt", ["purchase_order_id"]
    )
    op.create_index(
        "ix_procurement_vendor_invoice_purchase_order_id", "procurement_vendor_invoice", ["purchase_order_id"]
    )
    op.create_index("ix_procurement_vendor_invoice_vendor_id", "procurement_vendor_invoice", ["vendor_id"])
    op.create_index("ix_procurement_vendor_invoice_status", "procurement_vendor_invoice", ["status"])
    op.create_index(
        "ix_procurement_audit_entity", "procurement_audit_entry", ["organisation_id", "entity", "entity_id"]
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
