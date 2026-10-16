"""Initial inventory-equipment schema: categories, locations, items, units, stock levels, the stock ledger,
loans and loan lines. Every table carries organisation_id; on Postgres each gets the tenant_isolation
row-level-security policy (eos_core.rls.POLICY) through enable_rls().

Revision ID: ie_0001
Revises:
Create Date: 2026-10-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ie_0001"
down_revision = None
branch_labels = None
depends_on = None


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _updated() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "inventory_equipment_category",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("approver_user_ids", sa.JSON, nullable=False),
        sa.Column("default_loan_rules", sa.JSON, nullable=False),
        sa.UniqueConstraint("organisation_id", "name", name="uq_inventory_equipment_category_name"),
    )
    op.create_table(
        "inventory_equipment_location",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address", sa.String(300), nullable=True),
        sa.Column("keeper_user_ids", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
    )
    op.create_table(
        "inventory_equipment_item",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(60), nullable=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("inventory_equipment_category.id"), nullable=False),
        sa.Column("tracking", sa.String(20), nullable=False),
        sa.Column("unit_of_measure", sa.String(30), nullable=False),
        sa.Column("loanable", sa.Boolean, nullable=False),
        sa.Column("consumable", sa.Boolean, nullable=False),
        sa.Column("reorder_level", sa.Float, nullable=True),
        sa.Column("reorder_quantity", sa.Float, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("attributes", sa.JSON, nullable=False),
        sa.Column("image_document_id", sa.String(100), nullable=True),
        sa.Column("loan_rules", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("low_since", sa.DateTime(timezone=True), nullable=True),
        _updated(),
        sa.UniqueConstraint("organisation_id", "code", name="uq_inventory_equipment_item_code"),
    )
    op.create_table(
        "inventory_equipment_unit",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_equipment_item.id"), nullable=False),
        sa.Column("tag", sa.String(60), nullable=False),
        sa.Column("serial_number", sa.String(100), nullable=True),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("inventory_equipment_location.id"), nullable=True),
        sa.Column("condition", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("asset_id", sa.String(36), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("current_loan_id", sa.String(36), nullable=True),
        sa.UniqueConstraint("organisation_id", "tag", name="uq_inventory_equipment_unit_tag"),
    )
    op.create_table(
        "inventory_equipment_stock_level",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_equipment_item.id"), nullable=False),
        sa.Column("location_id", sa.String(36), sa.ForeignKey("inventory_equipment_location.id"), nullable=False),
        sa.Column("on_hand", sa.Float, nullable=False),
        sa.Column("reserved", sa.Float, nullable=False),
        sa.UniqueConstraint("organisation_id", "item_id", "location_id", name="uq_inventory_equipment_stock_level"),
    )
    op.create_table(
        "inventory_equipment_movement",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_equipment_item.id"), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit_ids", sa.JSON, nullable=False),
        sa.Column("from_location_id", sa.String(36), nullable=True),
        sa.Column("to_location_id", sa.String(36), nullable=True),
        sa.Column("issued_to", sa.String(36), nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("reference", sa.JSON, nullable=True),
        sa.Column("loan_id", sa.String(36), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        "inventory_equipment_loan",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("borrower_id", sa.String(36), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("purpose", sa.String(300), nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handed_out_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("handed_out_by", sa.String(36), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("extensions", sa.Integer, nullable=False),
        sa.Column("reference", sa.JSON, nullable=True),
        _updated(),
    )
    op.create_table(
        "inventory_equipment_loan_line",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("loan_id", sa.String(36), sa.ForeignKey("inventory_equipment_loan.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("inventory_equipment_item.id"), nullable=False),
        sa.Column("quantity", sa.Float, nullable=False),
        sa.Column("unit_id", sa.String(36), nullable=True),
        sa.Column("from_location_id", sa.String(36), nullable=True),
        sa.Column("condition_out", sa.String(20), nullable=True),
        sa.Column("condition_in", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("damage_note", sa.Text, nullable=True),
    )

    for table in (
        "inventory_equipment_category",
        "inventory_equipment_location",
        "inventory_equipment_item",
        "inventory_equipment_unit",
        "inventory_equipment_stock_level",
        "inventory_equipment_movement",
        "inventory_equipment_loan",
        "inventory_equipment_loan_line",
    ):
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_inventory_equipment_item_category_id", "inventory_equipment_item", ["category_id"])
    op.create_index("ix_inventory_equipment_unit_item_id", "inventory_equipment_unit", ["item_id"])
    op.create_index("ix_inventory_equipment_stock_level_item_id", "inventory_equipment_stock_level", ["item_id"])
    op.create_index("ix_inventory_equipment_movement_kind", "inventory_equipment_movement", ["kind"])
    op.create_index("ix_inventory_equipment_movement_item_id", "inventory_equipment_movement", ["item_id"])
    op.create_index("ix_inventory_equipment_loan_borrower_id", "inventory_equipment_loan", ["borrower_id"])
    op.create_index("ix_inventory_equipment_loan_status", "inventory_equipment_loan", ["status"])
    op.create_index("ix_inventory_equipment_loan_line_loan_id", "inventory_equipment_loan_line", ["loan_id"])

    enable_rls("inventory_equipment_category")
    enable_rls("inventory_equipment_location")
    enable_rls("inventory_equipment_item")
    enable_rls("inventory_equipment_unit")
    enable_rls("inventory_equipment_stock_level")
    enable_rls("inventory_equipment_movement")
    enable_rls("inventory_equipment_loan")
    enable_rls("inventory_equipment_loan_line")


def downgrade() -> None:
    for table in (
        "inventory_equipment_loan_line",
        "inventory_equipment_loan",
        "inventory_equipment_movement",
        "inventory_equipment_stock_level",
        "inventory_equipment_unit",
        "inventory_equipment_item",
        "inventory_equipment_location",
        "inventory_equipment_category",
    ):
        op.drop_table(table)
