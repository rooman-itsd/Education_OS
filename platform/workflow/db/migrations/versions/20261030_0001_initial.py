"""Initial workflow schema: chains, steps, requests, actions with tenant isolation RLS.

Revision ID: workflow_0001
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "workflow_0001"
down_revision = None
branch_labels = None
depends_on = None

CHAINS = "workflow_chain"
STEPS = "workflow_step"
REQUESTS = "workflow_request"
ACTIONS = "workflow_action"


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if _postgres():
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    # 1. workflow_chain
    op.create_table(
        CHAINS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_workflow_chain_org_code"),
    )
    op.create_index("ix_workflow_chain_organisation_id", CHAINS, ["organisation_id"])
    op.create_index("ix_workflow_chain_org", CHAINS, ["organisation_id"])
    enable_rls(CHAINS)

    # 2. workflow_step
    op.create_table(
        STEPS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("chain_id", sa.String(36), sa.ForeignKey(f"{CHAINS}.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(128), nullable=False),
        sa.Column("approver_role", sa.String(64), nullable=False),
        sa.Column("sla_hours", sa.Integer(), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("chain_id", "step_order", name="uq_workflow_step_chain_order"),
    )
    op.create_index("ix_workflow_step_organisation_id", STEPS, ["organisation_id"])
    op.create_index("ix_workflow_step_chain", STEPS, ["chain_id"])
    op.create_index("ix_workflow_step_org", STEPS, ["organisation_id"])
    enable_rls(STEPS)

    # 3. workflow_request
    op.create_table(
        REQUESTS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("chain_id", sa.String(36), sa.ForeignKey(f"{CHAINS}.id"), nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", sa.String(64), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("requester_id", sa.String(36), nullable=False),
        sa.Column("requester_name", sa.String(128), nullable=True),
        sa.Column("current_step_order", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current_step_deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("delegated_to", sa.String(36), nullable=True),
        sa.Column("client_token", sa.String(120), nullable=True),
        sa.Column("context", sa.JSON(), nullable=False),
    )
    op.create_index("ix_workflow_request_organisation_id", REQUESTS, ["organisation_id"])
    op.create_index("ix_workflow_request_org_status", REQUESTS, ["organisation_id", "status"])
    op.create_index("ix_workflow_request_org_entity", REQUESTS, ["organisation_id", "entity_type", "entity_id"])
    op.create_index("uq_workflow_request_org_token", REQUESTS, ["organisation_id", "client_token"], unique=True)
    enable_rls(REQUESTS)

    # 4. workflow_action
    op.create_table(
        ACTIONS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("request_id", sa.String(36), sa.ForeignKey(f"{REQUESTS}.id", ondelete="CASCADE"), nullable=False),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("step_name", sa.String(128), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        sa.Column("actor_name", sa.String(128), nullable=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("comments", sa.Text(), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_workflow_action_organisation_id", ACTIONS, ["organisation_id"])
    op.create_index("ix_workflow_action_req_occurred", ACTIONS, ["request_id", "occurred_at"])
    op.create_index("ix_workflow_action_org", ACTIONS, ["organisation_id"])
    enable_rls(ACTIONS)


def downgrade() -> None:
    op.drop_table(ACTIONS)
    op.drop_table(REQUESTS)
    op.drop_table(STEPS)
    op.drop_table(CHAINS)
