"""Initial regulatory-reports schema: obligations, filings and audit entries. Every table carries organisation_id; on
Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: regulatory_reports_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "regulatory_reports_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "regulatory_reports_obligation",
    "regulatory_reports_filing",
    "regulatory_reports_audit_entry",
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
        "regulatory_reports_obligation",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("authority", sa.String(120), nullable=False),
        sa.Column("portal_url", sa.String(2000), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("recurrence", sa.String(12), nullable=False),
        sa.Column("default_owner_id", sa.String(36), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "regulatory_reports_filing",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("obligation_id", sa.String(36), sa.ForeignKey("regulatory_reports_obligation.id"), nullable=False),
        sa.Column("period_label", sa.String(60), nullable=False),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("due_on", sa.Date, nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("preparation_notes", sa.Text, nullable=True),
        sa.Column("links", sa.JSON, nullable=False),
        sa.Column("review_comment", sa.Text, nullable=True),
        sa.Column("submitted_on", sa.Date, nullable=True),
        sa.Column("submission_reference", sa.String(120), nullable=True),
        sa.Column("submitted_by", sa.String(36), nullable=True),
        sa.Column("acknowledged_on", sa.Date, nullable=True),
        sa.Column("acknowledgement_reference", sa.String(120), nullable=True),
        sa.Column("not_applicable_reason", sa.Text, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint(
            "organisation_id", "obligation_id", "period_label", name="uq_regulatory_reports_filing_period"
        ),
    )
    op.create_table(
        "regulatory_reports_audit_entry",
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
    op.create_index(
        "ix_regulatory_reports_obligation_title", "regulatory_reports_obligation", ["organisation_id", "title"]
    )
    op.create_index("ix_regulatory_reports_filing_obligation_id", "regulatory_reports_filing", ["obligation_id"])
    op.create_index(
        "ix_regulatory_reports_filing_status_due",
        "regulatory_reports_filing",
        ["organisation_id", "status", "due_on"],
    )
    op.create_index("ix_regulatory_reports_filing_owner", "regulatory_reports_filing", ["organisation_id", "owner_id"])
    op.create_index(
        "ix_regulatory_reports_audit_entity",
        "regulatory_reports_audit_entry",
        ["organisation_id", "entity", "entity_id"],
    )

    _enable_rls("regulatory_reports_obligation")
    _enable_rls("regulatory_reports_filing")
    _enable_rls("regulatory_reports_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
