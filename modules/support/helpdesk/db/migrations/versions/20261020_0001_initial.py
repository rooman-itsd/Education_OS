"""Initial helpdesk schema: queues, categories, tickets, comments, ticket links, the per-organisation ticket number
sequence and audit entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation
row-level-security policy.

Revision ID: helpdesk_0001
Revises:
Create Date: 2026-10-20
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "helpdesk_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "helpdesk_queue",
    "helpdesk_category",
    "helpdesk_ticket",
    "helpdesk_comment",
    "helpdesk_ticket_link",
    "helpdesk_ticket_number_sequence",
    "helpdesk_audit_entry",
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
        "helpdesk_queue",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("member_ids", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "name", name="uq_helpdesk_queue_name"),
    )
    op.create_table(
        "helpdesk_category",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("helpdesk_category.id"), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("default_queue_id", sa.String(36), sa.ForeignKey("helpdesk_queue.id"), nullable=False),
        sa.Column("default_priority", sa.String(10), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "helpdesk_ticket",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("requester_id", sa.String(36), nullable=False),
        sa.Column("raised_by_id", sa.String(36), nullable=False),
        sa.Column("channel", sa.String(10), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("helpdesk_category.id"), nullable=False),
        sa.Column("queue_id", sa.String(36), sa.ForeignKey("helpdesk_queue.id"), nullable=False),
        sa.Column("assignee_id", sa.String(36), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("hold_reason", sa.String(30), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("attachment_document_ids", sa.JSON, nullable=False),
        sa.Column("resolution_note", sa.Text, nullable=True),
        sa.Column("duplicate_of", sa.String(36), sa.ForeignKey("helpdesk_ticket.id"), nullable=True),
        sa.Column("reopen_count", sa.Integer, nullable=False),
        sa.Column("satisfaction_rating", sa.Integer, nullable=True),
        sa.Column("feedback", sa.Text, nullable=True),
        _ts("updated_at"),
        _ts("first_responded_at", nullable=True),
        _ts("resolved_at", nullable=True),
        _ts("closed_at", nullable=True),
        sa.UniqueConstraint("organisation_id", "number", name="uq_helpdesk_ticket_number"),
    )
    op.create_table(
        "helpdesk_comment",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("helpdesk_ticket.id"), nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("author_is_requester", sa.Boolean, nullable=False),
        sa.Column("visibility", sa.String(10), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("attachment_document_ids", sa.JSON, nullable=False),
    )
    op.create_table(
        "helpdesk_ticket_link",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("ticket_id", sa.String(36), sa.ForeignKey("helpdesk_ticket.id"), nullable=False),
        sa.Column("module", sa.String(80), nullable=False),
        sa.Column("entity", sa.String(80), nullable=False),
        sa.Column("ref_id", sa.String(200), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.UniqueConstraint(
            "organisation_id", "ticket_id", "module", "entity", "ref_id", name="uq_helpdesk_ticket_link_target"
        ),
    )
    op.create_table(
        "helpdesk_ticket_number_sequence",
        sa.Column("organisation_id", sa.String(36), primary_key=True),
        sa.Column("last_number", sa.Integer, nullable=False),
    )
    op.create_table(
        "helpdesk_audit_entry",
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
        if table != "helpdesk_ticket_number_sequence":  # keyed by organisation_id already
            op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_helpdesk_category_parent_id", "helpdesk_category", ["parent_id"])
    op.create_index(
        "ix_helpdesk_ticket_open_counts", "helpdesk_ticket", ["organisation_id", "status", "priority", "queue_id"]
    )
    op.create_index("ix_helpdesk_ticket_requester", "helpdesk_ticket", ["organisation_id", "requester_id"])
    op.create_index("ix_helpdesk_ticket_assignee", "helpdesk_ticket", ["organisation_id", "assignee_id"])
    op.create_index("ix_helpdesk_comment_ticket_id", "helpdesk_comment", ["ticket_id"])
    op.create_index("ix_helpdesk_ticket_link_ticket_id", "helpdesk_ticket_link", ["ticket_id"])
    op.create_index("ix_helpdesk_audit_entity", "helpdesk_audit_entry", ["organisation_id", "entity", "entity_id"])

    _enable_rls("helpdesk_queue")
    _enable_rls("helpdesk_category")
    _enable_rls("helpdesk_ticket")
    _enable_rls("helpdesk_comment")
    _enable_rls("helpdesk_ticket_link")
    _enable_rls("helpdesk_ticket_number_sequence")
    _enable_rls("helpdesk_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
