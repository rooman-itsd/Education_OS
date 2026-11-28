"""The registration read model, `examinations_registration_ref` (PRD section 9): one row per course registration that
enrolment-registration confirmed or withdrew, kept by the `course-registration.confirmed` and `.withdrawn` consumers, and
the source of who may become a candidate (FR-7). Events arrive unordered, so a withdrawal can arrive before the
confirmation: the creation columns (`academic_period_id`, `registration_type`) are nullable until the confirmation
arrives. The table carries organisation_id and gets the tenant_isolation row-level-security policy on Postgres
(eos_core.rls.POLICY). No row is changed.

Revision ID: ex_0007
Revises: ex_0006
Create Date: 2026-11-28
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ex_0007"
down_revision = "ex_0006"
branch_labels = None
depends_on = None

P = "examinations_"
TABLE = f"{P}registration_ref"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("course_offering_id", sa.String(36), nullable=False),
        sa.Column("academic_period_id", sa.String(36), nullable=True),
        sa.Column("registration_type", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "registration_id", name="uq_examinations_registration_ref"),
    )
    op.create_index(f"ix_{TABLE}_organisation_id", TABLE, ["organisation_id"])
    op.create_index(f"ix_{TABLE}_offering", TABLE, ["organisation_id", "course_offering_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)
