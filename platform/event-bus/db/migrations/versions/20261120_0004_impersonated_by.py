"""The envelope's `impersonated_by` (security review N3, #672): the super admin who was really acting when the
event's `actor` is a user being impersonated. Null for every event before this revision and for every event not
raised under impersonation. outbox_event already carries organisation_id and its row-level security policy.

Revision ID: event_bus_0004
Revises: event_bus_0003
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "event_bus_0004"
down_revision = "event_bus_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("outbox_event") as batch:
        batch.add_column(sa.Column("impersonated_by", sa.String(36), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("outbox_event") as batch:
        batch.drop_column("impersonated_by")
