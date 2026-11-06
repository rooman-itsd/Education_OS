"""Initial iqac-accreditation schema: frameworks, metrics, cycles, responses, evidence, action items and audit
entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: iqac_accreditation_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "iqac_accreditation_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "iqac_accreditation_framework",
    "iqac_accreditation_metric",
    "iqac_accreditation_cycle",
    "iqac_accreditation_response",
    "iqac_accreditation_evidence",
    "iqac_accreditation_action_item",
    "iqac_accreditation_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "iqac_accreditation_framework",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "code", name="uq_iqac_accreditation_framework_code"),
    )
    op.create_table(
        "iqac_accreditation_metric",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("framework_id", sa.String(36), sa.ForeignKey("iqac_accreditation_framework.id"), nullable=False),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("criterion", sa.String(200), nullable=True),
        sa.Column("kind", sa.String(14), nullable=False),
        sa.Column("unit", sa.String(40), nullable=True),
        sa.Column("guidance", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "framework_id", "code", name="uq_iqac_accreditation_metric_code"),
    )
    op.create_table(
        "iqac_accreditation_cycle",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("framework_id", sa.String(36), sa.ForeignKey("iqac_accreditation_framework.id"), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("submitted_on", sa.Date, nullable=True),
        _ts("closed_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "iqac_accreditation_response",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("cycle_id", sa.String(36), sa.ForeignKey("iqac_accreditation_cycle.id"), nullable=False),
        sa.Column("metric_id", sa.String(36), sa.ForeignKey("iqac_accreditation_metric.id"), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("due_on", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("value", sa.Float, nullable=True),
        sa.Column("narrative", sa.Text, nullable=True),
        sa.Column("review_comment", sa.Text, nullable=True),
        _ts("submitted_at", nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        _ts("reviewed_at", nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "cycle_id", "metric_id", name="uq_iqac_accreditation_response_metric"),
    )
    op.create_table(
        "iqac_accreditation_evidence",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("response_id", sa.String(36), sa.ForeignKey("iqac_accreditation_response.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(9), nullable=False),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("reference", sa.JSON, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("added_by", sa.String(36), nullable=False),
        _ts("added_at"),
    )
    op.create_table(
        "iqac_accreditation_action_item",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("source", sa.String(120), nullable=True),
        sa.Column("cycle_id", sa.String(36), sa.ForeignKey("iqac_accreditation_cycle.id"), nullable=True),
        sa.Column("metric_id", sa.String(36), sa.ForeignKey("iqac_accreditation_metric.id"), nullable=True),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("due_on", sa.Date, nullable=False),
        sa.Column("status", sa.String(11), nullable=False),
        _ts("completed_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "iqac_accreditation_audit_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        _ts("occurred_at"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_iqac_accreditation_metric_framework_id", "iqac_accreditation_metric", ["framework_id"])
    op.create_index(
        "ix_iqac_accreditation_cycle_framework",
        "iqac_accreditation_cycle",
        ["organisation_id", "framework_id", "status"],
    )
    op.create_index("ix_iqac_accreditation_response_cycle_id", "iqac_accreditation_response", ["cycle_id"])
    op.create_index("ix_iqac_accreditation_response_metric_id", "iqac_accreditation_response", ["metric_id"])
    op.create_index(
        "ix_iqac_accreditation_response_owner",
        "iqac_accreditation_response",
        ["organisation_id", "owner_id", "status"],
    )
    op.create_index("ix_iqac_accreditation_response_due", "iqac_accreditation_response", ["organisation_id", "due_on"])
    op.create_index("ix_iqac_accreditation_evidence_response_id", "iqac_accreditation_evidence", ["response_id"])
    op.create_index(
        "ix_iqac_accreditation_action_item_status_due",
        "iqac_accreditation_action_item",
        ["organisation_id", "status", "due_on"],
    )
    op.create_index(
        "ix_iqac_accreditation_action_item_owner", "iqac_accreditation_action_item", ["organisation_id", "owner_id"]
    )
    op.create_index(
        "ix_iqac_accreditation_audit_entity",
        "iqac_accreditation_audit_entry",
        ["organisation_id", "entity", "entity_id"],
    )

    _enable_rls("iqac_accreditation_framework")
    _enable_rls("iqac_accreditation_metric")
    _enable_rls("iqac_accreditation_cycle")
    _enable_rls("iqac_accreditation_response")
    _enable_rls("iqac_accreditation_evidence")
    _enable_rls("iqac_accreditation_action_item")
    _enable_rls("iqac_accreditation_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
