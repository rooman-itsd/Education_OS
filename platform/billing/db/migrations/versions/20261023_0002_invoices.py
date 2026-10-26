"""Invoices: one row per paid subscription period, tenant-scoped with the tenant_isolation policy on Postgres.

Revision ID: billing_0002
Revises: billing_0001
Create Date: 2026-10-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "billing_0002"
down_revision = "billing_0001"
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "billing_invoice",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("subscription_id", sa.String(36), nullable=False),
        sa.Column("plan_id", sa.String(40), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("payment_reference", sa.String(100), nullable=True),
        sa.Column("document_id", sa.String(36), nullable=True),
    )
    op.create_index("ix_billing_invoice_organisation_id", "billing_invoice", ["organisation_id"])
    op.create_index("ix_billing_invoice_subscription_id", "billing_invoice", ["subscription_id"])
    enable_rls("billing_invoice")


def downgrade() -> None:
    op.drop_table("billing_invoice")
