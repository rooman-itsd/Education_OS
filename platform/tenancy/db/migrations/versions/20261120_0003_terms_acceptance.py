"""Consent at registration (DPDP, #148): the Terms of Service / Privacy Notice version an organisation's first
administrator accepted, when, and which user. No table is created here; tenancy_organisation stays the one table
without organisation_id (see tenancy_0001). Nullable: organisations registered before this have no record.

Revision ID: tenancy_0003
Revises: tenancy_0002
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenancy_0003"
down_revision = "tenancy_0002"
branch_labels = None
depends_on = None

COLUMNS = (
    sa.Column("terms_version", sa.String(40), nullable=True),
    sa.Column("terms_accepted_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("terms_accepted_by", sa.String(36), nullable=True),
)


def upgrade() -> None:
    with op.batch_alter_table("tenancy_organisation") as batch:
        for column in COLUMNS:
            batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("tenancy_organisation") as batch:
        for column in reversed(COLUMNS):
            batch.drop_column(column.name)
