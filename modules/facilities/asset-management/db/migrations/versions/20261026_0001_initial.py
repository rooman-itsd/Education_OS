"""Initial asset-management schema: categories, assets, transfers, verification cycles and lines, depreciation runs
and lines, disposals. Every table carries organisation_id; on Postgres each gets the tenant_isolation
row-level-security policy (eos_core.rls.POLICY) through enable_rls().

Revision ID: am_0001
Revises:
Create Date: 2026-10-26
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "am_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = (
    "asset_management_category",
    "asset_management_asset",
    "asset_management_transfer",
    "asset_management_cycle",
    "asset_management_cycle_line",
    "asset_management_depreciation_run",
    "asset_management_depreciation_line",
    "asset_management_disposal",
)


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _money(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.Numeric(14, 2), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        "asset_management_category",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("code", sa.String(20), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("depreciation", sa.JSON, nullable=False),
        sa.Column("verification_interval_months", sa.Integer, nullable=True),
        sa.UniqueConstraint("organisation_id", "name", name="uq_asset_management_category_name"),
    )
    op.create_table(
        "asset_management_asset",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("tag", sa.String(60), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("asset_management_category.id"), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("make", sa.String(100), nullable=True),
        sa.Column("model", sa.String(100), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.String(300), nullable=True),
        sa.Column("org_unit_id", sa.String(36), nullable=True),
        sa.Column("custodian_id", sa.String(36), nullable=True),
        sa.Column("condition", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("status_before_disposal", sa.String(20), nullable=True),
        sa.Column("acquisition", sa.JSON, nullable=False),
        _money("cost"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("in_service_date", sa.Date, nullable=False),
        sa.Column("warranty_until", sa.Date, nullable=True),
        sa.Column("amc_reference", sa.JSON, nullable=True),
        sa.Column("inventory_unit_id", sa.String(36), nullable=True),
        sa.Column("depreciation", sa.JSON, nullable=False),
        sa.Column("attributes", sa.JSON, nullable=False),
        sa.Column("photo_document_ids", sa.JSON, nullable=False),
        _money("accumulated_depreciation"),
        sa.Column("depreciated_to", sa.Date, nullable=True),
        sa.Column("last_verified_at", sa.Date, nullable=True),
        sa.Column("overdue_notified_for", sa.Date, nullable=True),
        sa.Column("disposed_on", sa.Date, nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "tag", name="uq_asset_management_asset_tag"),
    )
    op.create_table(
        "asset_management_transfer",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("asset_management_asset.id"), nullable=False),
        sa.Column("from_values", sa.JSON, nullable=False),
        sa.Column("to_values", sa.JSON, nullable=False),
        sa.Column("effective_on", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("source", sa.String(20), nullable=False),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        "asset_management_cycle",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("due_on", sa.Date, nullable=False),
        sa.Column("scope", sa.JSON, nullable=False),
        sa.Column("verifier_user_ids", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_note", sa.Text, nullable=True),
    )
    op.create_table(
        "asset_management_cycle_line",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("cycle_id", sa.String(36), sa.ForeignKey("asset_management_cycle.id"), nullable=False),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("asset_management_asset.id"), nullable=False),
        sa.Column("tag", sa.String(60), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("expected_location", sa.String(300), nullable=True),
        sa.Column("result", sa.String(20), nullable=False),
        sa.Column("observed_location", sa.String(300), nullable=True),
        sa.Column("condition", sa.String(10), nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("photo_document_id", sa.String(100), nullable=True),
        sa.Column("verified_by", sa.String(36), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("cycle_id", "asset_id", name="uq_asset_management_cycle_line_asset"),
    )
    op.create_table(
        "asset_management_depreciation_run",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("asset_count", sa.Integer, nullable=False),
        _money("total"),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("by_category", sa.JSON, nullable=False),
        sa.Column("category_ids", sa.JSON, nullable=False),
        sa.Column("calculated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("posted_by", sa.String(36), nullable=True),
        sa.Column("posted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "asset_management_depreciation_line",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("run_id", sa.String(36), sa.ForeignKey("asset_management_depreciation_run.id"), nullable=True),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("asset_management_asset.id"), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.Column("tag", sa.String(60), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        _money("opening_book_value"),
        _money("amount"),
        _money("closing_book_value"),
        sa.Column("kind", sa.String(10), nullable=False),
    )
    op.create_table(
        "asset_management_disposal",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("asset_id", sa.String(36), sa.ForeignKey("asset_management_asset.id"), nullable=False),
        sa.Column("method", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        _money("expected_proceeds", nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("disposed_on", sa.Date, nullable=True),
        _money("proceeds", nullable=True),
        _money("book_value_at_disposal", nullable=True),
        _money("gain_or_loss", nullable=True),
        sa.Column("recipient", sa.String(300), nullable=True),
        sa.Column("certificate_document_id", sa.String(100), nullable=True),
        sa.Column("completion_note", sa.Text, nullable=True),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    for table, column in (
        ("asset_management_asset", "category_id"),
        ("asset_management_asset", "org_unit_id"),
        ("asset_management_asset", "custodian_id"),
        ("asset_management_asset", "status"),
        ("asset_management_transfer", "asset_id"),
        ("asset_management_cycle", "status"),
        ("asset_management_cycle_line", "cycle_id"),
        ("asset_management_depreciation_run", "period_end"),
        ("asset_management_depreciation_line", "run_id"),
        ("asset_management_depreciation_line", "asset_id"),
        ("asset_management_disposal", "asset_id"),
        ("asset_management_disposal", "status"),
        ("asset_management_disposal", "requested_by"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])

    enable_rls("asset_management_category")
    enable_rls("asset_management_asset")
    enable_rls("asset_management_transfer")
    enable_rls("asset_management_cycle")
    enable_rls("asset_management_cycle_line")
    enable_rls("asset_management_depreciation_run")
    enable_rls("asset_management_depreciation_line")
    enable_rls("asset_management_disposal")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
