"""Relay state on the outbox: payload schema version, delivery attempts, the last failure, when an event was
delivered and when a failed one may be tried again, plus the index the relay's claim query runs on.

Every row already in the table was written before any relay existed, and no consumer has ever seen it. Those
rows are marked published here (published_at left null), so starting the relay does not deliver weeks of
history at once: a consumer reacting to an old registration, for example, would mail someone today about it.

Revision ID: event_bus_0002
Revises: event_bus_0001
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "event_bus_0002"
down_revision = "event_bus_0001"
branch_labels = None
depends_on = None

COLUMNS = ("version", "attempts", "last_error", "published_at", "next_attempt_at")


def upgrade() -> None:
    if op.get_bind().dialect.name == "postgresql":
        # FORCE ROW LEVEL SECURITY applies to the table's owner too: without the bypass a migration run by a
        # non-superuser owner would see no rows and mark nothing.
        op.execute("SELECT set_config('app.bypass_rls', 'on', true)")
    op.execute(sa.text("UPDATE outbox_event SET published = :yes WHERE published = :no").bindparams(yes=True, no=False))
    with op.batch_alter_table("outbox_event") as batch:
        batch.add_column(sa.Column("version", sa.Integer, nullable=False, server_default="1"))
        batch.add_column(sa.Column("attempts", sa.Integer, nullable=False, server_default="0"))
        batch.add_column(sa.Column("last_error", sa.Text, nullable=True))
        batch.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))
        batch.add_column(sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True))
    op.create_index("ix_outbox_event_published_occurred_at", "outbox_event", ["published", "occurred_at"])


def downgrade() -> None:
    op.drop_index("ix_outbox_event_published_occurred_at", table_name="outbox_event")
    with op.batch_alter_table("outbox_event") as batch:
        for column in reversed(COLUMNS):
            batch.drop_column(column)
