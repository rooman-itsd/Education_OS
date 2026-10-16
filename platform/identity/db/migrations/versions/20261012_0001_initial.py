"""Initial identity schema: users. organisation_id is NULL only for super admins; on Postgres the table
gets the tenant_isolation row-level-security policy.

Revision ID: identity_0001
Revises:
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "identity_0001"
down_revision = None
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "identity_user",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("password_hash", sa.String(300), nullable=False),
        sa.Column("roles", sa.JSON, nullable=False),
        sa.Column("is_super_admin", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("organisation_id", "email", name="uq_identity_user_org_email"),
    )
    op.create_index("ix_identity_user_organisation_id", "identity_user", ["organisation_id"])
    op.create_index("ix_identity_user_email", "identity_user", ["email"])
    enable_rls("identity_user")


def downgrade() -> None:
    op.drop_table("identity_user")
