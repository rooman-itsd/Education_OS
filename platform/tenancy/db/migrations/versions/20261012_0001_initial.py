"""Initial tenancy schema: organisations, registration tokens, per-organisation module state.
tenancy_organisation defines the tenants and so carries no organisation_id; the other two carry it and
get the tenant_isolation row-level-security policy on Postgres.

Revision ID: tenancy_0001
Revises:
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "tenancy_0001"
down_revision = None
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    # rls-exempt: tenancy_organisation: this table defines the tenants themselves, so it has no organisation_id
    op.create_table(
        "tenancy_organisation",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("slug", sa.String(40), nullable=False),
        sa.Column("academy_type", sa.String(60), nullable=False),
        sa.Column("requested_academy_type", sa.String(60), nullable=True),
        sa.Column("country", sa.String(2), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("status_reason", sa.String(500), nullable=True),
        sa.Column("settings", sa.JSON, nullable=False),
    )
    op.create_index("ix_tenancy_organisation_slug", "tenancy_organisation", ["slug"], unique=True)

    op.create_table(
        "tenancy_registration_token",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("token", sa.String(64), nullable=False),
        sa.Column("email", sa.String(254), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used", sa.Boolean, nullable=False),
    )
    op.create_index("ix_tenancy_registration_token_organisation_id", "tenancy_registration_token", ["organisation_id"])
    op.create_index("ix_tenancy_registration_token_token", "tenancy_registration_token", ["token"], unique=True)

    op.create_table(
        "tenancy_organisation_module",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("module", sa.String(120), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("override", sa.Boolean, nullable=False),
        sa.Column("reason", sa.String(500), nullable=True),
        sa.UniqueConstraint("organisation_id", "module", name="uq_tenancy_org_module"),
    )
    op.create_index(
        "ix_tenancy_organisation_module_organisation_id", "tenancy_organisation_module", ["organisation_id"]
    )

    enable_rls("tenancy_registration_token")
    enable_rls("tenancy_organisation_module")


def downgrade() -> None:
    op.drop_table("tenancy_organisation_module")
    op.drop_table("tenancy_registration_token")
    op.drop_table("tenancy_organisation")
