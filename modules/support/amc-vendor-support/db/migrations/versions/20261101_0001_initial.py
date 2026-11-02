"""Initial amc-vendor-support schema: contracts, covered items, engagements, the per-organisation number sequence and
audit entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security
policy.

Revision ID: amc_vendor_support_0001
Revises:
Create Date: 2026-11-01
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "amc_vendor_support_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "amc_vendor_support_contract",
    "amc_vendor_support_covered_item",
    "amc_vendor_support_engagement",
    "amc_vendor_support_number_sequence",
    "amc_vendor_support_audit_entry",
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
        "amc_vendor_support_contract",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("vendor_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("coverage_type", sa.String(20), nullable=False),
        sa.Column("scope", sa.Text, nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("value_amount", sa.Numeric(14, 2), nullable=True),
        sa.Column("value_currency", sa.String(3), nullable=True),
        sa.Column("purchase_order_reference", sa.JSON, nullable=True),
        sa.Column("response_hours", sa.Integer, nullable=True),
        sa.Column("resolution_hours", sa.Integer, nullable=True),
        sa.Column("preventive_visits_per_year", sa.Integer, nullable=True),
        sa.Column("vendor_contacts", sa.JSON, nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("renewal_notice_days", sa.Integer, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("renewed_from_id", sa.String(36), nullable=True),
        sa.Column("renewed_to_id", sa.String(36), nullable=True),
        _ts("activated_at", nullable=True),
        _ts("terminated_at", nullable=True),
        sa.Column("termination_effective_date", sa.Date, nullable=True),
        sa.Column("termination_reason", sa.Text, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "number", name="uq_amc_vendor_support_contract_number"),
    )
    op.create_table(
        "amc_vendor_support_covered_item",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("amc_vendor_support_contract.id"), nullable=False),
        sa.Column("description", sa.String(200), nullable=False),
        sa.Column("ref_module", sa.String(60), nullable=True),
        sa.Column("ref_entity", sa.String(60), nullable=True),
        sa.Column("ref_id", sa.String(100), nullable=True),
        sa.UniqueConstraint(
            "organisation_id",
            "contract_id",
            "ref_module",
            "ref_entity",
            "ref_id",
            name="uq_amc_vendor_support_covered_item_reference",
        ),
    )
    op.create_table(
        "amc_vendor_support_engagement",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("contract_id", sa.String(36), sa.ForeignKey("amc_vendor_support_contract.id"), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("covered_item_id", sa.String(36), nullable=True),
        sa.Column("references", sa.JSON, nullable=False),
        sa.Column("vendor_call_reference", sa.String(100), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        _ts("reported_at"),
        _ts("vendor_responded_at", nullable=True),
        _ts("resolved_at", nullable=True),
        sa.Column("resolution_note", sa.Text, nullable=True),
        _ts("closed_at", nullable=True),
        sa.Column("raised_by", sa.String(36), nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "number", name="uq_amc_vendor_support_engagement_number"),
    )
    op.create_table(
        "amc_vendor_support_number_sequence",
        sa.Column("organisation_id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("last_number", sa.Integer, nullable=False),
    )
    op.create_table(
        "amc_vendor_support_audit_entry",
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
        if table != "amc_vendor_support_number_sequence":  # keyed by organisation_id already
            op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_amc_vendor_support_contract_vendor_id", "amc_vendor_support_contract", ["vendor_id"])
    op.create_index(
        "ix_amc_vendor_support_contract_status_end",
        "amc_vendor_support_contract",
        ["organisation_id", "status", "end_date"],
    )
    op.create_index(
        "ix_amc_vendor_support_covered_item_contract_id", "amc_vendor_support_covered_item", ["contract_id"]
    )
    op.create_index(
        "ix_amc_vendor_support_covered_item_reference",
        "amc_vendor_support_covered_item",
        ["organisation_id", "ref_module", "ref_entity", "ref_id"],
    )
    op.create_index(
        "ix_amc_vendor_support_engagement_contract",
        "amc_vendor_support_engagement",
        ["organisation_id", "contract_id", "status"],
    )
    op.create_index(
        "ix_amc_vendor_support_audit_entity",
        "amc_vendor_support_audit_entry",
        ["organisation_id", "entity", "entity_id"],
    )

    _enable_rls("amc_vendor_support_contract")
    _enable_rls("amc_vendor_support_covered_item")
    _enable_rls("amc_vendor_support_engagement")
    _enable_rls("amc_vendor_support_number_sequence")
    _enable_rls("amc_vendor_support_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
