"""Initial reporting schema: report definitions, executions, metric snapshots, and RLS.

Revision ID: reporting_0001
Revises:
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "reporting_0001"
down_revision = None
branch_labels = None
depends_on = None

DEFINITIONS = "reporting_definition"
EXECUTIONS = "reporting_execution"
SNAPSHOTS = "reporting_metric_snapshot"


def _postgres() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if _postgres():
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    # 1. reporting_definition
    op.create_table(
        DEFINITIONS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("code", sa.String(64), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=True),
        sa.Column("category", sa.String(64), nullable=False, server_default="general"),
        sa.Column("parameters_schema", sa.JSON(), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_reporting_definition_org_code"),
    )
    op.create_index("ix_reporting_definition_organisation_id", DEFINITIONS, ["organisation_id"])
    op.create_index("ix_reporting_definition_category", DEFINITIONS, ["category"])
    enable_rls(DEFINITIONS)

    # 2. reporting_execution
    op.create_table(
        EXECUTIONS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("report_definition_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending"),
        sa.Column("parameters", sa.JSON(), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("export_file_id", sa.String(36), nullable=True),
        sa.Column("error_message", sa.String(1000), nullable=True),
        sa.Column("client_token", sa.String(120), nullable=True),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_reporting_execution_organisation_id", EXECUTIONS, ["organisation_id"])
    op.create_index(
        "uq_reporting_execution_org_client_token",
        EXECUTIONS,
        ["organisation_id", "client_token"],
        unique=True,
        postgresql_where=sa.text("client_token IS NOT NULL"),
        sqlite_where=sa.text("client_token IS NOT NULL"),
    )
    op.create_index("ix_reporting_execution_def_status", EXECUTIONS, ["report_definition_id", "status"])
    enable_rls(EXECUTIONS)

    # 3. reporting_metric_snapshot
    op.create_table(
        SNAPSHOTS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("metric_type", sa.String(64), nullable=False),
        sa.Column("department_id", sa.String(64), nullable=True),
        sa.Column("period", sa.String(32), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reporting_metric_snapshot_organisation_id", SNAPSHOTS, ["organisation_id"])
    op.create_index(
        "ix_reporting_metric_snapshot_org_metric", SNAPSHOTS, ["organisation_id", "metric_type", "department_id"]
    )
    op.create_index("ix_reporting_metric_snapshot_period", SNAPSHOTS, ["period"])
    enable_rls(SNAPSHOTS)


def downgrade() -> None:
    op.drop_table(SNAPSHOTS)
    op.drop_table(EXECUTIONS)
    op.drop_table(DEFINITIONS)
