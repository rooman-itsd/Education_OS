"""MetricSnapshot ingestion: the fact ledger and the reshaped snapshot table.

reporting_metric_snapshot had no writer anywhere (#317 audit, F1), so it has never held data in a deployment
(reporting is not enabled, so this chain has not run there either). It is replaced, not altered, with the agreed
logical fields: tenant (organisation_id), source_module, metric_key, period_start, period_end, dimensions (JSONB on
PostgreSQL), value, unit, calculated_at, schema_version; unique per (organisation, metric, period, dimensions,
schema_version). reporting_metric_fact is the idempotent ledger snapshots are recalculated from (unique per source
event and metric). Both carry organisation_id with the tenant_isolation policy.

Revision ID: reporting_0003
Revises: reporting_0002
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY
from sqlalchemy.dialects import postgresql

revision = "reporting_0003"
down_revision = "reporting_0002"
branch_labels = None
depends_on = None

DIMENSIONS = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def _rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.drop_table("reporting_metric_snapshot")
    op.create_table(
        "reporting_metric_snapshot",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("source_module", sa.String(64), nullable=False),
        sa.Column("metric_key", sa.String(96), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("dimensions", DIMENSIONS, nullable=False),
        sa.Column("dimensions_key", sa.String(512), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("unit", sa.String(32), nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("schema_version", sa.Integer(), nullable=False),
        sa.UniqueConstraint(
            "organisation_id", "metric_key", "period_start", "period_end", "dimensions_key", "schema_version",
            name="uq_reporting_metric_snapshot_cell",
        ),
    )  # fmt: skip
    op.create_index("ix_reporting_metric_snapshot_organisation_id", "reporting_metric_snapshot", ["organisation_id"])
    op.create_index(
        "ix_reporting_metric_snapshot_org_metric_period",
        "reporting_metric_snapshot",
        ["organisation_id", "metric_key", "period_start"],
    )
    _rls("reporting_metric_snapshot")

    op.create_table(
        "reporting_metric_fact",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("source_module", sa.String(64), nullable=False),
        sa.Column("metric_key", sa.String(96), nullable=False),
        sa.Column("metric_version", sa.Integer(), nullable=False),
        sa.Column("source_event_id", sa.String(36), nullable=False),
        sa.Column("source_ref", sa.String(64), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("dimensions", DIMENSIONS, nullable=False),
        sa.Column("dimensions_key", sa.String(512), nullable=False),
        sa.Column("value", sa.Numeric(18, 4), nullable=False),
        sa.Column("ingested_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("source_event_id", "metric_key", name="uq_reporting_metric_fact_event_metric"),
    )
    op.create_index("ix_reporting_metric_fact_organisation_id", "reporting_metric_fact", ["organisation_id"])
    op.create_index(
        "ix_reporting_metric_fact_org_metric_time",
        "reporting_metric_fact",
        ["organisation_id", "metric_key", "occurred_at"],
    )
    op.create_index(
        "ix_reporting_metric_fact_source_ref", "reporting_metric_fact", ["organisation_id", "metric_key", "source_ref"]
    )
    _rls("reporting_metric_fact")


def downgrade() -> None:
    op.drop_table("reporting_metric_fact")
    op.drop_table("reporting_metric_snapshot")
    op.create_table(
        "reporting_metric_snapshot",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("metric_type", sa.String(64), nullable=False),
        sa.Column("department_id", sa.String(64), nullable=True),
        sa.Column("period", sa.String(32), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("captured_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_reporting_metric_snapshot_organisation_id", "reporting_metric_snapshot", ["organisation_id"])
    op.create_index(
        "ix_reporting_metric_snapshot_org_metric",
        "reporting_metric_snapshot",
        ["organisation_id", "metric_type", "department_id"],
    )
    op.create_index("ix_reporting_metric_snapshot_period", "reporting_metric_snapshot", ["period"])
    _rls("reporting_metric_snapshot")
