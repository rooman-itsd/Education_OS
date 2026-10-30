"""Deletion with retention (DPDP): a super admin's DELETE archives an organisation and records when its rows
may be purged, who asked and which status to restore. No table is created here; tenancy_organisation stays
the one table without organisation_id (see tenancy_0001).

Revision ID: tenancy_0002
Revises: tenancy_0001
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "tenancy_0002"
down_revision = "tenancy_0001"
branch_labels = None
depends_on = None

COLUMNS = (
    sa.Column("delete_after", sa.DateTime(timezone=True), nullable=True),
    sa.Column("deletion_requested_by", sa.String(36), nullable=True),
    sa.Column("deletion_requested_at", sa.DateTime(timezone=True), nullable=True),
    sa.Column("status_before_deletion", sa.String(30), nullable=True),
)


def upgrade() -> None:
    with op.batch_alter_table("tenancy_organisation") as batch:
        for column in COLUMNS:
            batch.add_column(column)


def downgrade() -> None:
    with op.batch_alter_table("tenancy_organisation") as batch:
        for column in reversed(COLUMNS):
            batch.drop_column(column.name)
