"""Add the optional title of an exam paper (contract `ExamPaper.title`, `updateExamPaper`).

One nullable column on an existing tenant table: no new table, so no new row-level-security policy (the policy of
`examinations_exam_paper` from ex_0001 covers it) and no backfill (existing papers have no title). Nullable and
without a default, so the upgrade is a metadata-only change on Postgres and no row is rewritten. Batch mode makes the
same revision work on SQLite, which the module's tests use.

Revision ID: ex_0002
Revises: ex_0001
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "ex_0002"
down_revision = "ex_0001"
branch_labels = None
depends_on = None

TABLE = "examinations_exam_paper"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("title", sa.String(200), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.drop_column("title")
