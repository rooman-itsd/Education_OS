"""One live duty per staff member, duty type and target (FR-9; the duplicate rule of the duties API).

Two partial unique indexes on `examinations_exam_duty`, one for duties on a session and one for duties on a paper, each
over (organisation_id, staff_id, duty_type, target) and only for `assigned` and `completed` rows, so a cancelled duty can
be assigned again. They back the application's duplicate check against two concurrent requests. No new table, so no new
row-level-security policy, and no data is changed.

Safety: the upgrade fails if the table already holds two live duties for one staff member, type and target. Nothing
could write duties before this revision (no operation created them), so a database populated through the API has none.
Downgrade drops the two indexes.

Revision ID: ex_0003
Revises: ex_0002
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ex_0003"
down_revision = "ex_0002"
branch_labels = None
depends_on = None

TABLE = "examinations_exam_duty"
LIVE = "status IN ('assigned', 'completed')"
INDEXES = (
    ("uq_examinations_duty_session_live", "exam_session_id"),
    ("uq_examinations_duty_paper_live", "exam_paper_id"),
)


def upgrade() -> None:
    for name, target in INDEXES:
        where = sa.text(f"{target} IS NOT NULL AND {LIVE}")
        op.create_index(
            name,
            TABLE,
            ["organisation_id", "staff_id", "duty_type", target],
            unique=True,
            postgresql_where=where,
            sqlite_where=where,
        )


def downgrade() -> None:
    for name, _ in reversed(INDEXES):
        op.drop_index(name, table_name=TABLE)
