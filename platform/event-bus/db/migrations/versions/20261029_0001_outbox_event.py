"""The transactional outbox table, exactly as eos_core's model created it before this chain existed: id, tenant,
name, actor, payload, occurred_at, published; on Postgres, the tenant_isolation row-level security policy.

A database the API already started on has the table (eos_core.db.init_db created it from the model), so this
revision leaves it alone and is simply recorded; 0002 then brings both kinds of database to the same head.

Revision ID: event_bus_0001
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "event_bus_0001"
down_revision = None
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per transaction (eos_core.rls.POLICY).
    A platform-level event (organisation_id null) is written and read only in platform scope."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    if sa.inspect(op.get_bind()).has_table("outbox_event"):
        return
    op.create_table(
        "outbox_event",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("payload", sa.JSON, nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published", sa.Boolean, nullable=False),
    )
    op.create_index("ix_outbox_event_organisation_id", "outbox_event", ["organisation_id"])
    op.create_index("ix_outbox_event_name", "outbox_event", ["name"])
    enable_rls("outbox_event")


def downgrade() -> None:
    op.drop_index("ix_outbox_event_name", table_name="outbox_event")
    op.drop_index("ix_outbox_event_organisation_id", table_name="outbox_event")
    op.drop_table("outbox_event")
