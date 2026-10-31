"""Applicant accounts: admissions_application.applicant_user_id records the identity user who linked the application
to their account (POST /me/applications), so the Applicant dashboard can show a signed-in applicant their own
applications. Nullable: applications are still submitted anonymously and stay unlinked until the applicant links
them. No new table; admissions_application keeps its tenant_isolation row-level-security policy.

Revision ID: admissions_0002
Revises: admissions_0001
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "admissions_0002"
down_revision = "admissions_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("admissions_application", sa.Column("applicant_user_id", sa.String(36), nullable=True))
    op.create_index(
        "ix_admissions_application_applicant_user",
        "admissions_application",
        ["organisation_id", "applicant_user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_admissions_application_applicant_user", table_name="admissions_application")
    # SQLite cannot drop a column in place; batch mode copies the table there and is a plain ALTER on Postgres.
    with op.batch_alter_table("admissions_application") as batch:
        batch.drop_column("applicant_user_id")
