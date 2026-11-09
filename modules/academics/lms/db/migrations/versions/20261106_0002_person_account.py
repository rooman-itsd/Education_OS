"""person_account: which student-information person a sign-in account is, from student-information's
person.account-linked. A learner's own reads map their identity user id to the person id their registrations carry.
The table carries organisation_id; on Postgres it gets the tenant_isolation row-level-security policy, forced.

Revision ID: lms_0002
Revises: lms_0001
Create Date: 2026-11-06
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "lms_0002"
down_revision = "lms_0001"
branch_labels = None
depends_on = None


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "lms_person_account",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("identity_user_id", sa.String(36), nullable=True),
        sa.Column("linked_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "person_id", name="uq_lms_person_account"),
    )
    op.create_index("ix_lms_person_account_organisation_id", "lms_person_account", ["organisation_id"])
    op.create_index("ix_lms_person_account_user", "lms_person_account", ["organisation_id", "identity_user_id"])
    _enable_rls("lms_person_account")


def downgrade() -> None:
    op.drop_index("ix_lms_person_account_user", table_name="lms_person_account")
    op.drop_index("ix_lms_person_account_organisation_id", table_name="lms_person_account")
    op.drop_table("lms_person_account")
