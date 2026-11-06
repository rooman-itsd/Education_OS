"""Read model for the student-information consumer: `person_account`, which student-information person a sign-in
account is (person.account-linked). A student's own reads map their identity user id to the person id
`section_member.student_id` holds. The table carries organisation_id and gets the tenant_isolation row-level-security
policy on Postgres (eos_core.rls.POLICY).

Revision ID: tt_0004
Revises: tt_0003
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "tt_0004"
down_revision = "tt_0003"
branch_labels = None
depends_on = None

P = "timetable_attendance_"
NEW_TABLES = [f"{P}person_account"]


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        f"{P}person_account",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("identity_user_id", sa.String(36), nullable=True),
        sa.Column("linked_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "person_id", name="uq_timetable_attendance_person_account"),
    )
    for table in NEW_TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
        enable_rls(table)
    op.create_index(
        "ix_timetable_attendance_person_account_user", f"{P}person_account", ["organisation_id", "identity_user_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_timetable_attendance_person_account_user", table_name=f"{P}person_account")
    for table in reversed(NEW_TABLES):
        op.drop_index(f"ix_{table}_organisation_id", table_name=table)
        op.drop_table(table)
