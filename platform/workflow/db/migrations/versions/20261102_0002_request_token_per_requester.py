"""Scope request client_token idempotency to the requester.

The unique index was (organisation_id, client_token), so a second user replaying a token got the first user's
request back, context included. It becomes (organisation_id, requester_id, client_token). Widening a unique key
never fails on existing rows, so upgrade is safe on a populated table.

Revision ID: workflow_0002
Revises: workflow_0001
Create Date: 2026-11-02
"""

from __future__ import annotations

from alembic import op

revision = "workflow_0002"
down_revision = "workflow_0001"
branch_labels = None
depends_on = None

REQUESTS = "workflow_request"
OLD = "uq_workflow_request_org_token"
NEW = "uq_workflow_request_org_requester_token"


def upgrade() -> None:
    op.drop_index(OLD, table_name=REQUESTS)
    op.create_index(NEW, REQUESTS, ["organisation_id", "requester_id", "client_token"], unique=True)


def downgrade() -> None:
    # Fails if two requesters in one organisation have since used the same token; resolve those rows first.
    op.drop_index(NEW, table_name=REQUESTS)
    op.create_index(OLD, REQUESTS, ["organisation_id", "client_token"], unique=True)
