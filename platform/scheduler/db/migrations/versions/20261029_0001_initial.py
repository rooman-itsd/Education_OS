"""Initial scheduler schema: schedules and their runs. Both carry organisation_id (null for a platform schedule
and its runs, which exist only in platform scope) and, on Postgres, the tenant_isolation row-level security policy.

Revision ID: scheduler_0001
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "scheduler_0001"
down_revision = None
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per transaction (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "scheduler_schedule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("job", sa.String(120), nullable=False),
        sa.Column("scope", sa.String(20), nullable=False),
        sa.Column("cron", sa.String(120), nullable=True),
        sa.Column("timezone", sa.String(64), nullable=True),
        sa.Column("run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("arguments", sa.JSON, nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("allow_overlap", sa.Boolean, nullable=False),
        sa.Column("catch_up", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_status", sa.String(20), nullable=True),
    )
    op.create_index("ix_scheduler_schedule_organisation_id", "scheduler_schedule", ["organisation_id"])
    op.create_index("ix_scheduler_schedule_job", "scheduler_schedule", ["job"])
    op.create_index("ix_scheduler_schedule_next_run_at", "scheduler_schedule", ["next_run_at"])
    enable_rls("scheduler_schedule")

    op.create_table(
        "scheduler_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column(
            "schedule_id", sa.String(36), sa.ForeignKey("scheduler_schedule.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("job", sa.String(120), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_ms", sa.Integer, nullable=True),
        sa.Column("missed_windows", sa.Integer, nullable=False),
        sa.Column("detail", sa.Text, nullable=True),
    )
    op.create_index("ix_scheduler_run_organisation_id", "scheduler_run", ["organisation_id"])
    op.create_index("ix_scheduler_run_schedule_id", "scheduler_run", ["schedule_id"])
    op.create_index("ix_scheduler_run_status", "scheduler_run", ["status"])
    op.create_index("ix_scheduler_run_started_at", "scheduler_run", ["started_at"])
    enable_rls("scheduler_run")


def downgrade() -> None:
    op.drop_table("scheduler_run")
    op.drop_table("scheduler_schedule")
