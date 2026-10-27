"""Initial maintenance schema: categories, tickets, the work log and preventive schedules. Every table carries
organisation_id; on Postgres each gets the tenant_isolation row-level-security policy (eos_core.rls.POLICY)
through enable_rls().

Revision ID: mt_0001
Revises:
Create Date: 2026-10-23
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "mt_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ("maintenance_category", "maintenance_ticket", "maintenance_work_entry", "maintenance_schedule")


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _updated() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)


def _target() -> list[sa.Column]:
    return [
        sa.Column("target_kind", sa.String(20), nullable=False),
        sa.Column("target_id", sa.String(100), nullable=True),
        sa.Column("target_label", sa.String(300), nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "maintenance_category",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_priority", sa.String(10), nullable=False),
        sa.Column("default_assignee_ids", sa.JSON, nullable=False),
        sa.Column("sla_override", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", "name", name="uq_maintenance_category_name"),
    )
    op.create_table(
        "maintenance_ticket",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("maintenance_category.id"), nullable=False),
        *_target(),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("blocks_use", sa.Boolean, nullable=False),
        sa.Column("reported_by", sa.String(36), nullable=False),
        sa.Column("assignee_id", sa.String(36), nullable=True),
        sa.Column("vendor", sa.JSON, nullable=True),
        sa.Column("hold_reason", sa.String(20), nullable=True),
        sa.Column("held_since", sa.DateTime(timezone=True), nullable=True),
        sa.Column("held_minutes", sa.Integer, nullable=False),
        sa.Column("schedule_id", sa.String(36), nullable=True),
        sa.Column("source", sa.JSON, nullable=True),
        sa.Column("photo_document_ids", sa.JSON, nullable=False),
        sa.Column("checklist", sa.JSON, nullable=False),
        sa.Column("response_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolution_due_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("response_breached", sa.Boolean, nullable=False),
        sa.Column("resolution_breached", sa.Boolean, nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resolution", sa.JSON, nullable=True),
        sa.Column("rating", sa.Integer, nullable=True),
        sa.Column("feedback", sa.Text, nullable=True),
        _updated(),
        sa.UniqueConstraint("organisation_id", "number", name="uq_maintenance_ticket_number"),
    )
    op.create_table(
        "maintenance_work_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("maintenance_ticket.id"), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("minutes", sa.Integer, nullable=True),
        sa.Column("item_id", sa.String(36), nullable=True),
        sa.Column("item_name", sa.String(200), nullable=True),
        sa.Column("quantity", sa.Numeric(12, 3), nullable=True),
        sa.Column("cost_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("cost_currency", sa.String(3), nullable=True),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        "maintenance_schedule",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("maintenance_category.id"), nullable=False),
        *_target(),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("every", sa.Integer, nullable=False),
        sa.Column("unit", sa.String(10), nullable=False),
        sa.Column("next_due_on", sa.Date, nullable=False),
        sa.Column("lead_days", sa.Integer, nullable=False),
        sa.Column("priority", sa.String(10), nullable=True),
        sa.Column("default_assignee_id", sa.String(36), nullable=True),
        sa.Column("checklist", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("open_ticket_id", sa.String(36), nullable=True),
        sa.Column("last_completed_on", sa.Date, nullable=True),
        _updated(),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_maintenance_ticket_category_id", "maintenance_ticket", ["category_id"])
    op.create_index("ix_maintenance_ticket_status", "maintenance_ticket", ["status"])
    op.create_index("ix_maintenance_ticket_reported_by", "maintenance_ticket", ["reported_by"])
    op.create_index("ix_maintenance_ticket_assignee_id", "maintenance_ticket", ["assignee_id"])
    op.create_index("ix_maintenance_ticket_schedule_id", "maintenance_ticket", ["schedule_id"])
    op.create_index("ix_maintenance_work_entry_ticket_id", "maintenance_work_entry", ["ticket_id"])
    op.create_index("ix_maintenance_schedule_category_id", "maintenance_schedule", ["category_id"])

    enable_rls("maintenance_category")
    enable_rls("maintenance_ticket")
    enable_rls("maintenance_work_entry")
    enable_rls("maintenance_schedule")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
