"""Delivery tracked per consuming module (#83's consumer group per module).

event_bus_delivery holds one row per (event, module): delivered, or failed with its attempts and last error. The
relay then retries only the modules that failed, and one failing consumer no longer holds the event back from the
others. organisation_id is the event's, with the same row-level security as every module table.

Existing events need no rows: a published event is never delivered again, and a pending one simply has no module
marked delivered yet, which is how it was handled before.

Revision ID: event_bus_0003
Revises: event_bus_0002
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "event_bus_0003"
down_revision = "event_bus_0002"
branch_labels = None
depends_on = None

TABLE = "event_bus_delivery"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.String(36), sa.ForeignKey("outbox_event.id", ondelete="CASCADE"), nullable=False),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_error", sa.Text, nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("event_id", "module", name="uq_event_bus_delivery_event_module"),
    )
    op.create_index("ix_event_bus_delivery_organisation_id", TABLE, ["organisation_id"])
    op.create_index("ix_event_bus_delivery_event", TABLE, ["event_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)
