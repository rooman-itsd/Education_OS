"""Scope report-run client_token idempotency to the requester.

The partial unique index was (organisation_id, client_token), so a second user replaying a token got the first
user's run back, including its result_summary. It becomes (organisation_id, requested_by, client_token). Widening a
unique key never fails on existing rows, so upgrade is safe on a populated table.

Revision ID: reporting_0002
Revises: reporting_0001
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "reporting_0002"
down_revision = "reporting_0001"
branch_labels = None
depends_on = None

EXECUTIONS = "reporting_execution"
OLD = "uq_reporting_execution_org_client_token"
NEW = "uq_reporting_execution_org_requester_token"
WHERE = sa.text("client_token IS NOT NULL")


def upgrade() -> None:
    op.drop_index(OLD, table_name=EXECUTIONS)
    op.create_index(
        NEW,
        EXECUTIONS,
        ["organisation_id", "requested_by", "client_token"],
        unique=True,
        postgresql_where=WHERE,
        sqlite_where=WHERE,
    )


def downgrade() -> None:
    # Fails if two requesters in one organisation have since used the same token; resolve those rows first.
    op.drop_index(NEW, table_name=EXECUTIONS)
    op.create_index(
        OLD, EXECUTIONS, ["organisation_id", "client_token"], unique=True, postgresql_where=WHERE, sqlite_where=WHERE
    )
