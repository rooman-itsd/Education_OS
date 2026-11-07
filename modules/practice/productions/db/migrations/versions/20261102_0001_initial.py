"""Initial productions schema: productions, the parts and crew jobs people hold on them, and the
preparation tasks behind each one. Every table carries organisation_id; on Postgres each gets the
tenant_isolation row-level-security policy (eos_core.rls.POLICY) through enable_rls().

Revision ID: pr_0001
Revises:
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "pr_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ("productions_production", "productions_role", "productions_task")


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "productions_production",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("department", sa.String(120), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("venue", sa.String(200), nullable=True),
        sa.Column("resource_id", sa.String(36), nullable=True),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("call_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lead_user_id", sa.String(36), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("client_token", sa.String(100), nullable=True),
        sa.Column("cancelled_reason", sa.Text, nullable=True),
        sa.Column("cancelled_by", sa.String(36), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        # One caller's idempotency key, never shared across callers.
        sa.UniqueConstraint("organisation_id", "created_by", "client_token", name="uq_productions_client_token"),
    )
    op.create_table(
        "productions_role",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("production_id", sa.String(36), sa.ForeignKey("productions_production.id"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("role_name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("assigned_by", sa.String(36), nullable=False),
        sa.Column("responded_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "production_id", "user_id", "role_name", name="uq_productions_role"),
    )
    op.create_table(
        "productions_task",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("production_id", sa.String(36), sa.ForeignKey("productions_production.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assignee_user_id", sa.String(36), nullable=True),
        sa.Column("added_by", sa.String(36), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_by", sa.String(36), nullable=True),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_productions_production_kind", "productions_production", ["kind"])
    op.create_index("ix_productions_production_status", "productions_production", ["status"])
    op.create_index("ix_productions_production_department", "productions_production", ["department"])
    op.create_index("ix_productions_production_starts_at", "productions_production", ["starts_at"])
    op.create_index("ix_productions_production_lead_user_id", "productions_production", ["lead_user_id"])
    op.create_index("ix_productions_role_production_id", "productions_role", ["production_id"])
    op.create_index("ix_productions_role_user_id", "productions_role", ["user_id"])
    op.create_index("ix_productions_role_status", "productions_role", ["status"])
    op.create_index("ix_productions_task_production_id", "productions_task", ["production_id"])
    op.create_index("ix_productions_task_status", "productions_task", ["status"])

    # Named one by one, not in a loop: tools/scripts/check-migrations.py reads the table name out of the call.
    enable_rls("productions_production")
    enable_rls("productions_role")
    enable_rls("productions_task")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
