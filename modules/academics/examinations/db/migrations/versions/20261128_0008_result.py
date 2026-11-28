"""The result table, `examinations_result` (PRD FR-13 to FR-17): one row per version of a student's result in a course
offering and exam cycle. A revision adds a row and turns the previous one `superseded`; no row is deleted. The table
carries organisation_id and gets the tenant_isolation row-level-security policy on Postgres (eos_core.rls.POLICY). No row
is changed.

Revision ID: ex_0008
Revises: ex_0007
Create Date: 2026-11-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ex_0008"
down_revision = "ex_0007"
branch_labels = None
depends_on = None

P = "examinations_"
TABLE = f"{P}result"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("exam_cycle_id", sa.String(36), sa.ForeignKey(f"{P}exam_cycle.id"), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("course_offering_id", sa.String(36), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("components", sa.JSON, nullable=False),
        sa.Column("weighted_percent", sa.Numeric(5, 2), nullable=False),
        sa.Column("grade", sa.String(20), nullable=False),
        sa.Column("grade_point", sa.Numeric(5, 2), nullable=False),
        sa.Column("passed", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("computed_by", sa.String(36), nullable=True),
        sa.Column("department_approved_by", sa.String(36), nullable=True),
        sa.Column("department_approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approved_by", sa.String(36), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revision_reason", sa.String(500), nullable=True),
        sa.Column("revised_by", sa.String(36), nullable=True),
        sa.UniqueConstraint(
            "organisation_id",
            "exam_cycle_id",
            "student_id",
            "course_offering_id",
            "version",
            name="uq_examinations_result_version",
        ),
    )
    op.create_index(f"ix_{TABLE}_organisation_id", TABLE, ["organisation_id"])
    op.create_index(f"ix_{TABLE}_cycle", TABLE, ["organisation_id", "exam_cycle_id", "status"])
    op.create_index(f"ix_{TABLE}_student", TABLE, ["organisation_id", "student_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)
