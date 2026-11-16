"""The candidate table (PRD 5.6): one student's candidacy for one exam paper. Schema only: no migration of data, and
nothing writes or reads the table yet (registration consumers, candidate creation, eligibility and the listing come later).

The unique key `(organisation_id, exam_paper_id, student_id)` implements the PRD rule "One per (exam paper, student)"
within an organisation: `organisation_id` is part of the key. Nothing yet ties a candidate's organisation to its paper's
organisation, so future candidate-creation logic must set the candidate's organisation from the paper.
`organisation_id` is NOT NULL on this table only, so that the key cannot be bypassed by a NULL organisation (a NULL
member makes every row distinct on Postgres and SQLite). `student_id` carries the canonical `person_id`.
`eligibility_status` and `eligibility_reasons` have no default. `pending_inputs` is not stored. The table gets the tenant_isolation
row-level-security policy on Postgres (eos_core.rls.POLICY).

Revision ID: ex_0005
Revises: ex_0004
Create Date: 2026-11-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ex_0005"
down_revision = "ex_0004"
branch_labels = None
depends_on = None

P = "examinations_"
TABLE = f"{P}candidate"


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exam_cycle_id", sa.String(36), sa.ForeignKey(f"{P}exam_cycle.id"), nullable=False),
        sa.Column("exam_paper_id", sa.String(36), sa.ForeignKey(f"{P}exam_paper.id"), nullable=False),
        sa.Column("course_offering_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("eligibility_status", sa.String(20), nullable=False),
        sa.Column("eligibility_reasons", sa.JSON(none_as_null=True), nullable=False),
        sa.Column("overridden_by", sa.String(36), nullable=True),
        sa.Column("override_reason", sa.String(500), nullable=True),
        sa.Column("determined_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organisation_id", "exam_paper_id", "student_id", name="uq_examinations_candidate_paper_student"
        ),
    )
    op.create_index(f"ix_{TABLE}_organisation_id", TABLE, ["organisation_id"])
    op.create_index(f"ix_{TABLE}_exam_cycle_id", TABLE, ["exam_cycle_id"])
    enable_rls(TABLE)


def downgrade() -> None:
    op.drop_table(TABLE)
