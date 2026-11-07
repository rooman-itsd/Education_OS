"""GST tax invoices: invoice number series per financial year, tax breakdown and parties on the invoice, and the
organisation's billing profile (the recipient).

Invoices issued before this keep null in every new column: they were not tax invoices and are not renumbered.

Revision ID: billing_0004
Revises: billing_0003
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "billing_0004"
down_revision = "billing_0003"
branch_labels = None
depends_on = None


def new_columns() -> list[sa.Column]:
    return [
        sa.Column("invoice_number", sa.String(16), nullable=True),
        sa.Column("financial_year", sa.String(5), nullable=True),
        sa.Column("tax_scheme", sa.String(5), nullable=True),
        sa.Column("sac_code", sa.String(6), nullable=True),
        sa.Column("gst_rate", sa.Numeric(5, 2), nullable=True),
        sa.Column("taxable_value", sa.Numeric(12, 2), nullable=True),
        sa.Column("cgst_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("sgst_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("igst_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("total_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("place_of_supply", sa.String(2), nullable=True),
        sa.Column("supplier_name", sa.String(200), nullable=True),
        sa.Column("supplier_gstin", sa.String(15), nullable=True),
        sa.Column("supplier_address", sa.String(500), nullable=True),
        sa.Column("supplier_state_code", sa.String(2), nullable=True),
        sa.Column("recipient_name", sa.String(200), nullable=True),
        sa.Column("recipient_gstin", sa.String(15), nullable=True),
        sa.Column("recipient_address", sa.String(500), nullable=True),
        sa.Column("recipient_state_code", sa.String(2), nullable=True),
    ]


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    with op.batch_alter_table("billing_invoice") as batch:
        for col in new_columns():
            batch.add_column(col)
        batch.create_unique_constraint("uq_billing_invoice_number", ["invoice_number"])
    # rls-exempt: billing_invoice_counter: the platform is the one supplier and the series is platform-wide; no tenant rows
    op.create_table(
        "billing_invoice_counter",
        sa.Column("financial_year", sa.String(5), primary_key=True),
        sa.Column("last_sequence", sa.Integer, nullable=False),
    )
    op.create_table(
        "billing_profile",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=False),
        sa.Column("gstin", sa.String(15), nullable=True),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column("state_code", sa.String(2), nullable=True),
        sa.UniqueConstraint("organisation_id", name="uq_billing_profile_organisation"),
    )
    op.create_index("ix_billing_profile_organisation_id", "billing_profile", ["organisation_id"])
    enable_rls("billing_profile")


def downgrade() -> None:
    op.drop_table("billing_profile")
    op.drop_table("billing_invoice_counter")
    with op.batch_alter_table("billing_invoice") as batch:
        batch.drop_constraint("uq_billing_invoice_number", type_="unique")
        for col in new_columns():
            batch.drop_column(col.name)
