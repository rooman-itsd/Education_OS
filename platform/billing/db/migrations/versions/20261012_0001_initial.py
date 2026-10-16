"""Initial billing schema: plans and subscriptions. Plans are platform-wide and carry no organisation_id;
subscriptions carry it and get the tenant_isolation row-level-security policy on Postgres.

Revision ID: billing_0001
Revises:
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "billing_0001"
down_revision = None
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    # rls-exempt: billing_plan: platform-wide price list managed by the super admin; it holds no tenant rows
    op.create_table(
        "billing_plan",
        sa.Column("id", sa.String(40), primary_key=True),
        sa.Column("title", sa.String(100), nullable=False),
        sa.Column("description", sa.String(500), nullable=False),
        sa.Column("price_per_month", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("trial_days", sa.Integer, nullable=True),
        sa.Column("suites", sa.JSON, nullable=False),
        sa.Column("modules", sa.JSON, nullable=False),
        sa.Column("specialized_suites", sa.String(10), nullable=False),
        sa.Column("integrations", sa.JSON, nullable=False),
        sa.Column("limits", sa.JSON, nullable=False),
        sa.Column("after_trial", sa.String(20), nullable=False),
        sa.Column("published", sa.Boolean, nullable=False),
    )
    op.create_table(
        "billing_subscription",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("plan_id", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trial_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_period_ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("comped_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("pending_plan_id", sa.String(40), nullable=True),
        sa.Column("payment_reference", sa.String(100), nullable=True),
    )
    op.create_index("ix_billing_subscription_organisation_id", "billing_subscription", ["organisation_id"])
    enable_rls("billing_subscription")


def downgrade() -> None:
    op.drop_table("billing_subscription")
    op.drop_table("billing_plan")
