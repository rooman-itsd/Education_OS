"""Initial payment-sbiepay schema: merchant accounts, payments, refunds, reconciliation runs, notifications.
Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: psb_0001
Revises:
Create Date: 2026-10-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "psb_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "payment_sbiepay_"
TABLES = ["merchant_account", "payment", "refund", "reconciliation_run", "notification"]
OPEN = sa.text("status IN ('created', 'pending')")


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _money(name: str) -> sa.Column:
    return sa.Column(name, sa.Numeric(12, 2), nullable=False)


def upgrade() -> None:
    op.create_table(
        f"{P}merchant_account",
        _id(),
        _org(),
        sa.Column("merchant_id", sa.String(100), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("encryption_key_ciphertext", sa.Text, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", name="uq_payment_sbiepay_merchant_org"),
    )
    op.create_table(
        f"{P}payment",
        _id(),
        _org(),
        _ts("created_at"),
        sa.Column("reference", sa.String(40), nullable=False),
        sa.Column("purpose", sa.String(20), nullable=False),
        sa.Column("source_module", sa.String(60), nullable=False),
        sa.Column("source_reference", sa.String(100), nullable=False),
        sa.Column("merchant_id", sa.String(100), nullable=False),
        _money("amount"),
        _money("refunded_amount"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("description", sa.String(100), nullable=False),
        sa.Column("payer", sa.JSON, nullable=False),
        sa.Column("return_url", sa.String(2000), nullable=False),
        sa.Column("notify_url", sa.String(2000), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("gateway_transaction_id", sa.String(100), nullable=True),
        sa.Column("payment_mode", sa.String(40), nullable=True),
        sa.Column("failure_reason", sa.String(300), nullable=True),
        sa.Column("initiated_by", sa.String(36), nullable=True),
        _ts("expires_at"),
        _ts("completed_at", nullable=True),
        _ts("settled_at", nullable=True),
    )
    op.create_table(
        f"{P}refund",
        _id(),
        _org(),
        sa.Column("payment_id", sa.String(36), nullable=False),
        sa.Column("reference", sa.String(40), nullable=False),
        _money("amount"),
        sa.Column("reason", sa.String(300), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("gateway_refund_id", sa.String(100), nullable=True),
        sa.Column("failure_reason", sa.String(300), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        _ts("requested_at"),
    )
    op.create_table(
        f"{P}reconciliation_run",
        _id(),
        _org(),
        sa.Column("settlement_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("matched", sa.Integer, nullable=False),
        sa.Column("mismatches", sa.JSON, nullable=False),
        sa.Column("failure_reason", sa.String(300), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=True),
        _ts("started_at"),
        _ts("finished_at", nullable=True),
    )
    op.create_table(
        f"{P}notification",
        _id(),
        _org(),
        _ts("created_at"),
        sa.Column("event_id", sa.String(36), nullable=False, unique=True),
        sa.Column("payment_id", sa.String(36), nullable=False),
        sa.Column("url", sa.String(2000), nullable=False),
        sa.Column("body", sa.JSON, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        _ts("next_attempt_at"),
        _ts("delivered_at", nullable=True),
        sa.Column("last_error", sa.String(300), nullable=True),
    )
    for table in TABLES:
        op.create_index(f"ix_{P}{table}_organisation_id", f"{P}{table}", ["organisation_id"])
    op.create_index(f"ix_{P}payment_reference", f"{P}payment", ["reference"], unique=True)
    op.create_index(f"ix_{P}payment_source_module", f"{P}payment", ["source_module"])
    op.create_index(f"ix_{P}payment_source_reference", f"{P}payment", ["source_reference"])
    op.create_index(f"ix_{P}payment_status", f"{P}payment", ["status"])
    op.create_index(f"ix_{P}payment_gateway_transaction_id", f"{P}payment", ["gateway_transaction_id"])
    # One open payment per organisation and caller source (see Payment.__table_args__).
    op.create_index(
        "uq_payment_sbiepay_open_source",
        f"{P}payment",
        ["organisation_id", "source_module", "source_reference"],
        unique=True,
        sqlite_where=OPEN,
        postgresql_where=OPEN,
    )
    op.create_index(f"ix_{P}refund_payment_id", f"{P}refund", ["payment_id"])
    op.create_index(f"ix_{P}refund_reference", f"{P}refund", ["reference"])
    op.create_index(f"ix_{P}reconciliation_run_settlement_date", f"{P}reconciliation_run", ["settlement_date"])
    op.create_index(f"ix_{P}notification_payment_id", f"{P}notification", ["payment_id"])
    op.create_index(f"ix_{P}notification_next_attempt_at", f"{P}notification", ["next_attempt_at"])
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
