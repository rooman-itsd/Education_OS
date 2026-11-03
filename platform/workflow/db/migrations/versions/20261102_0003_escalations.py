"""SLA escalations: one row per request step that missed its deadline.

workflow.sla-check (scheduler job) records an escalation and publishes workflow.step.overdue; the unique
(request_id, step_order) keeps a step from being escalated twice, including two checks running at once.

Revision ID: workflow_0003
Revises: workflow_0002
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "workflow_0003"
down_revision = "workflow_0002"
branch_labels = None
depends_on = None

TABLE = "workflow_escalation"


def upgrade() -> None:
    op.create_table(
        TABLE,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column(
            "request_id", sa.String(36), sa.ForeignKey("workflow_request.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("step_order", sa.Integer(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=False),
        sa.Column("overdue_seconds", sa.Integer(), nullable=False),
        sa.Column("escalated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("request_id", "step_order", name="uq_workflow_escalation_request_step"),
    )
    op.create_index("ix_workflow_escalation_organisation_id", TABLE, ["organisation_id"])
    op.create_index("ix_workflow_escalation_org", TABLE, ["organisation_id"])
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=TABLE))


def downgrade() -> None:
    op.drop_table(TABLE)
