"""Record which platform defaults were seeded, so seeding happens once per job.

seed_platform_defaults() checked "no schedule for this job yet" and inserted, with no lock or unique key: two
schedulers starting together both created the schedule (reproduced 20 out of 20 times on PostgreSQL), so the job
ran twice per window from then on; and a seeded schedule an operator deleted came back on the next restart.
scheduler_seeded_default is keyed on the job; seeding inserts there first and creates the schedule only if that
insert succeeded.

Backfill: every job that already has a platform schedule counts as seeded, so an existing deployment is not
seeded again (and any duplicates already there are left for an operator to remove; see the README).

Revision ID: scheduler_0002
Revises: scheduler_0001
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "scheduler_0002"
down_revision = "scheduler_0001"
branch_labels = None
depends_on = None

TABLE = "scheduler_seeded_default"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("job", sa.String(120), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("seeded_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scheduler_seeded_default_organisation_id", TABLE, ["organisation_id"])
    postgres = op.get_bind().dialect.name == "postgresql"
    if postgres:
        # FORCE ROW LEVEL SECURITY binds the owner too: platform rows (organisation_id null) need the bypass.
        op.execute("SELECT set_config('app.bypass_rls', 'on', true)")
    op.execute(
        "INSERT INTO scheduler_seeded_default (job, organisation_id, seeded_at) "
        "SELECT job, NULL, MIN(created_at) FROM scheduler_schedule "
        "WHERE scope = 'platform' AND organisation_id IS NULL GROUP BY job"
    )
    if postgres:
        op.execute(POLICY.format(table=TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)
