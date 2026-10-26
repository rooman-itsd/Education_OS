"""Audit trail: academic_management_audit_entry records who changed what and when, for every state change, until the
audit SDK exists. Its columns follow platform/audit's Record contract (client_token, entity_type, summary, changed
fields before and after) so rows can be backfilled to platform/audit idempotently. Carries organisation_id and gets
the tenant_isolation row-level-security policy on Postgres.

Revision ID: am_0002
Revises: am_0001
Create Date: 2026-10-24
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "am_0002"
down_revision = "am_0001"
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "academic_management_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("client_token", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_academic_management_audit_client_token"),
    )
    op.create_index(
        "ix_academic_management_audit_entry_organisation_id", "academic_management_audit_entry", ["organisation_id"]
    )
    op.create_index(
        "ix_academic_management_audit_entity",
        "academic_management_audit_entry",
        ["organisation_id", "entity_type", "entity_id"],
    )
    enable_rls("academic_management_audit_entry")


def downgrade() -> None:
    op.drop_table("academic_management_audit_entry")
