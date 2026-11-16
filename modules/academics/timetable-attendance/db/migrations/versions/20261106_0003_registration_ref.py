"""Read model for the enrolment-registration consumers: `registration_ref` (the facts of one course registration,
from which its section memberships are rebuilt) and `section_member.registration_id` (which registration a membership
comes from). The new table carries organisation_id and gets the tenant_isolation row-level-security policy on Postgres
(eos_core.rls.POLICY); `section_member` already has it.

Revision ID: tt_0003
Revises: tt_0002
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "tt_0003"
down_revision = "tt_0002"
branch_labels = None
depends_on = None

P = "timetable_attendance_"
NEW_TABLES = [f"{P}registration_ref"]


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        f"{P}registration_ref",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registration_id", sa.String(36), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("course_offering_id", sa.String(36), nullable=False),
        sa.Column("section_id", sa.String(36), nullable=True),
        sa.Column("confirmed_on", sa.Date, nullable=True),
        sa.Column("withdrawn_on", sa.Date, nullable=True),
        sa.Column("moves", sa.JSON, nullable=False),
        sa.Column("student_name", sa.String(200), nullable=True),
        sa.Column("name_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "registration_id", name="uq_timetable_attendance_registration_ref"),
    )
    for table in NEW_TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
        enable_rls(table)
    with op.batch_alter_table(f"{P}section_member") as batch:
        batch.add_column(sa.Column("registration_id", sa.String(36), nullable=True))
        batch.create_index("ix_timetable_attendance_member_registration", ["organisation_id", "registration_id"])


def downgrade() -> None:
    with op.batch_alter_table(f"{P}section_member") as batch:
        batch.drop_index("ix_timetable_attendance_member_registration")
        batch.drop_column("registration_id")
    for table in reversed(NEW_TABLES):
        op.drop_table(table)
