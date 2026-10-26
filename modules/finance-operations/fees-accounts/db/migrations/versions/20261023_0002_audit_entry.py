"""Audit trail: fees_accounts_audit_entry records who changed what and when, for every state change, until the audit
SDK exists. Carries organisation_id and gets the tenant_isolation row-level-security policy on Postgres.

Revision ID: fees_accounts_0002
Revises: fees_accounts_0001
Create Date: 2026-10-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "fees_accounts_0002"
down_revision = "fees_accounts_0001"
branch_labels = None
depends_on = None


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "fees_accounts_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    _enable_rls("fees_accounts_audit_entry")
    op.create_index("ix_fees_accounts_audit_entry_organisation_id", "fees_accounts_audit_entry", ["organisation_id"])
    op.create_index(
        "ix_fees_accounts_audit_entity", "fees_accounts_audit_entry", ["organisation_id", "entity", "entity_id"]
    )


def downgrade() -> None:
    op.drop_table("fees_accounts_audit_entry")
