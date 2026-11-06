"""Initial sla-management schema: business-hours calendars, SLA policies, the helpdesk tickets known from events,
clocks, escalations, processed helpdesk event ids and audit entries. Every table carries organisation_id; on Postgres
each gets the tenant_isolation row-level-security policy.

Revision ID: sla_management_0001
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "sla_management_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "sla_management_calendar",
    "sla_management_policy",
    "sla_management_ticket_ref",
    "sla_management_clock",
    "sla_management_escalation",
    "sla_management_processed_event",
    "sla_management_audit_entry",
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
        "sla_management_calendar",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("time_zone", sa.String(64), nullable=False),
        sa.Column("always_open", sa.Boolean, nullable=False),
        sa.Column("working_hours", sa.JSON, nullable=False),
        sa.Column("holidays", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "sla_management_policy",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=True),
        sa.Column("category_key", sa.String(36), nullable=False),
        sa.Column("calendar_id", sa.String(36), sa.ForeignKey("sla_management_calendar.id"), nullable=False),
        sa.Column("response_target_minutes", sa.Integer, nullable=False),
        sa.Column("resolution_target_minutes", sa.Integer, nullable=False),
        sa.Column("warning_percent", sa.Integer, nullable=False),
        sa.Column("pause_on_hold_reasons", sa.JSON, nullable=False),
        sa.Column("escalation_levels", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "sla_management_ticket_ref",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("number", sa.String(40), nullable=True),
        sa.Column("priority", sa.String(10), nullable=True),
        sa.Column("category_id", sa.String(36), nullable=True),
        sa.Column("queue_id", sa.String(36), nullable=True),
        sa.Column("assignee_id", sa.String(36), nullable=True),
        sa.Column("created", sa.Boolean, nullable=False),
        sa.Column("final", sa.Boolean, nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "ticket_id", name="uq_sla_management_ticket_ref_ticket"),
    )
    op.create_table(
        "sla_management_clock",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("ticket_id", sa.String(36), nullable=False),
        sa.Column("ticket_number", sa.String(40), nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("policy_id", sa.String(36), nullable=False),
        sa.Column("calendar_id", sa.String(36), nullable=False),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("category_id", sa.String(36), nullable=True),
        sa.Column("queue_id", sa.String(36), nullable=True),
        sa.Column("assignee_id", sa.String(36), nullable=True),
        sa.Column("target_minutes", sa.Integer, nullable=False),
        sa.Column("warning_percent", sa.Integer, nullable=False),
        sa.Column("pause_on_hold_reasons", sa.JSON, nullable=False),
        sa.Column("escalation_levels", sa.JSON, nullable=False),
        sa.Column("business_minutes_used", sa.Integer, nullable=False),
        _ts("run_started_at", nullable=True),
        sa.Column("state", sa.String(10), nullable=False),
        _ts("started_at"),
        _ts("warn_at", nullable=True),
        _ts("due_at", nullable=True),
        _ts("paused_at", nullable=True),
        _ts("stopped_at", nullable=True),
        sa.Column("outcome", sa.String(10), nullable=True),
        sa.Column("warned", sa.Boolean, nullable=False),
        sa.Column("breached", sa.Boolean, nullable=False),
        _ts("breached_at", nullable=True),
        sa.Column("escalated_level", sa.Integer, nullable=False),
        _ts("next_escalation_at", nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "ticket_id", "kind", name="uq_sla_management_clock_ticket_kind"),
    )
    op.create_table(
        "sla_management_escalation",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("clock_id", sa.String(36), sa.ForeignKey("sla_management_clock.id"), nullable=False),
        sa.Column("level", sa.Integer, nullable=False),
        _ts("sent_at"),
        sa.Column("recipient_ids", sa.JSON, nullable=False),
        sa.UniqueConstraint("organisation_id", "clock_id", "level", name="uq_sla_management_escalation"),
    )
    op.create_table(
        "sla_management_processed_event",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        _ts("processed_at"),
        sa.UniqueConstraint("organisation_id", "event_id", name="uq_sla_management_processed_event"),
    )
    op.create_table(
        "sla_management_audit_entry",
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
        "uq_sla_management_policy_active",
        "sla_management_policy",
        ["organisation_id", "priority", "category_key"],
        unique=True,
        sqlite_where=sa.text("active"),
        postgresql_where=sa.text("active"),
    )
    op.create_index("ix_sla_management_policy_calendar_id", "sla_management_policy", ["calendar_id"])
    op.create_index("ix_sla_management_clock_state_due", "sla_management_clock", ["organisation_id", "state", "due_at"])
    op.create_index("ix_sla_management_escalation_clock_id", "sla_management_escalation", ["clock_id"])
    op.create_index(
        "ix_sla_management_audit_entity", "sla_management_audit_entry", ["organisation_id", "entity", "entity_id"]
    )

    _enable_rls("sla_management_calendar")
    _enable_rls("sla_management_policy")
    _enable_rls("sla_management_ticket_ref")
    _enable_rls("sla_management_clock")
    _enable_rls("sla_management_escalation")
    _enable_rls("sla_management_processed_event")
    _enable_rls("sla_management_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
