"""Trial reminders raised, so a missed one is caught up and none is raised twice.

remind_trials() raised billing.trial.expiring only when a trial had exactly 7, 3 or 1 days left: a day the
scheduler missed lost that reminder for good. billing_trial_reminder records each reminder raised (organisation,
trial end date, threshold; unique); the job now raises the most urgent due threshold with no row yet.

No backfill: reminders raised before this carry the same reminder_key format, so notification's per-key
deduplication still keeps a reminder from being mailed twice.

Revision ID: billing_0003
Revises: billing_0002
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "billing_0003"
down_revision = "billing_0002"
branch_labels = None
depends_on = None

TABLE = "billing_trial_reminder"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("trial_ends_on", sa.String(10), nullable=False),
        sa.Column("threshold", sa.Integer, nullable=False),
        sa.Column("days_left", sa.Integer, nullable=False),
        sa.Column("raised_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "trial_ends_on", "threshold", name="uq_billing_trial_reminder"),
    )
    op.create_index("ix_billing_trial_reminder_organisation_id", TABLE, ["organisation_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)
