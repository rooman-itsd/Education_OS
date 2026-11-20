"""The mark entry table (PRD FR-10 to FR-12): one candidate's marks for their paper, entered, moderated and locked.

One row per candidate: `UNIQUE (candidate_id)` on a globally unique id, so the key has no nullable `organisation_id`
member. `candidate_id` is a foreign key to `examinations_candidate` (inside the module). `marks_obtained` is NULL when
`absent`; `moderation_delta` is the moderator's adjustment to the original marks, which are never changed. No default
on any column. The table gets the tenant_isolation row-level-security policy on Postgres (eos_core.rls.POLICY).

Revision ID: ex_0006
Revises: ex_0005
Create Date: 2026-11-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ex_0006"
down_revision = "ex_0005"
branch_labels = None
depends_on = None

P = "examinations_"
TABLE = f"{P}mark_entry"
MARKS = sa.Numeric(8, 2, asdecimal=True)


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey(f"{P}candidate.id"), nullable=False),
        sa.Column("marks_obtained", MARKS, nullable=True),
        sa.Column("absent", sa.Boolean(), nullable=False),
        sa.Column("entered_by", sa.String(36), nullable=False),
        sa.Column("entered_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("moderation_delta", MARKS, nullable=True),
        sa.Column("moderation_reason", sa.String(500), nullable=True),
        sa.Column("moderated_by", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("candidate_id", name="uq_examinations_mark_entry_candidate"),
    )
    op.create_index(f"ix_{TABLE}_organisation_id", TABLE, ["organisation_id"])
    enable_rls(TABLE)


def downgrade() -> None:
    op.drop_table(TABLE)
