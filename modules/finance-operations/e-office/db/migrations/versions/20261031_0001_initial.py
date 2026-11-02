"""Initial e-office schema: file categories, files with the people who have held them, the note sheet, attachments,
movement history, inward receipts, outward dispatches and the audit trail. Every table carries organisation_id; on
Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: e_office_0001
Revises:
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "e_office_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "e_office_category",
    "e_office_file",
    "e_office_file_holder",
    "e_office_note",
    "e_office_attachment",
    "e_office_movement",
    "e_office_receipt",
    "e_office_dispatch",
    "e_office_audit_entry",
]


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "e_office_category",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("retention_years", sa.Integer, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_e_office_category_code"),
    )
    _enable_rls("e_office_category")

    op.create_table(
        "e_office_file",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("year", sa.Integer, nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("category_id", sa.String(36), sa.ForeignKey("e_office_category.id"), nullable=False),
        sa.Column("department_id", sa.String(36), nullable=True),
        sa.Column("priority", sa.String(10), nullable=False),
        sa.Column("confidential", sa.Boolean, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("holder_id", sa.String(36), nullable=False),
        _ts("held_since"),
        sa.Column("action_required", sa.String(200), nullable=True),
        sa.Column("due_on", sa.Date, nullable=True),
        _ts("overdue_flagged_at", nullable=True),
        sa.Column("last_decision", sa.String(10), nullable=True),
        _ts("closed_at", nullable=True),
        sa.Column("closed_by", sa.String(36), nullable=True),
        sa.UniqueConstraint("organisation_id", "number", name="uq_e_office_file_number"),
    )
    _enable_rls("e_office_file")

    op.create_table(
        "e_office_file_holder",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("e_office_file.id"), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        _ts("first_held_at"),
        sa.UniqueConstraint("file_id", "user_id", name="uq_e_office_file_holder"),
    )
    _enable_rls("e_office_file_holder")

    op.create_table(
        "e_office_note",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("e_office_file.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("text", sa.Text, nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("attachment_ids", sa.JSON, nullable=False),
        sa.UniqueConstraint("file_id", "sequence", name="uq_e_office_note_sequence"),
    )
    _enable_rls("e_office_note")

    op.create_table(
        "e_office_attachment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("e_office_file.id"), nullable=False),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("title", sa.String(300), nullable=False),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("receipt_id", sa.String(36), nullable=True),
        sa.Column("added_by", sa.String(36), nullable=False),
    )
    _enable_rls("e_office_attachment")

    op.create_table(
        "e_office_movement",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("e_office_file.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("kind", sa.String(10), nullable=False),
        sa.Column("from_user_id", sa.String(36), nullable=True),
        sa.Column("to_user_id", sa.String(36), nullable=False),
        sa.Column("remark", sa.Text, nullable=True),
        sa.Column("action_required", sa.String(200), nullable=True),
        sa.Column("due_on", sa.Date, nullable=True),
        sa.Column("held_seconds", sa.Integer, nullable=False),
        _ts("at"),
        sa.UniqueConstraint("file_id", "sequence", name="uq_e_office_movement_sequence"),
    )
    _enable_rls("e_office_movement")

    op.create_table(
        "e_office_receipt",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("received_on", sa.Date, nullable=False),
        sa.Column("sender", sa.String(300), nullable=False),
        sa.Column("sender_reference", sa.String(200), nullable=True),
        sa.Column("subject", sa.String(500), nullable=False),
        sa.Column("mode", sa.String(10), nullable=True),
        sa.Column("document_id", sa.String(100), nullable=True),
        sa.Column("send_to_user_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("e_office_file.id"), nullable=True),
        sa.Column("registered_by", sa.String(36), nullable=False),
        sa.Column("attached_by", sa.String(36), nullable=True),
        _ts("attached_at", nullable=True),
        sa.UniqueConstraint("organisation_id", "number", name="uq_e_office_receipt_number"),
    )
    _enable_rls("e_office_receipt")

    op.create_table(
        "e_office_dispatch",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("file_id", sa.String(36), sa.ForeignKey("e_office_file.id"), nullable=False),
        sa.Column("attachment_id", sa.String(36), sa.ForeignKey("e_office_attachment.id"), nullable=False),
        sa.Column("addressee", sa.String(300), nullable=False),
        sa.Column("address", sa.Text, nullable=True),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("mode", sa.String(10), nullable=True),
        sa.Column("sent_on", sa.Date, nullable=True),
        sa.Column("reference", sa.String(200), nullable=True),
        sa.Column("requested_by", sa.String(36), nullable=False),
        sa.Column("sent_by", sa.String(36), nullable=True),
        sa.UniqueConstraint("organisation_id", "number", name="uq_e_office_dispatch_number"),
    )
    _enable_rls("e_office_dispatch")

    op.create_table(
        "e_office_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )
    _enable_rls("e_office_audit_entry")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_e_office_file_status", "e_office_file", ["status"])
    op.create_index("ix_e_office_file_holder_id", "e_office_file", ["holder_id"])
    op.create_index("ix_e_office_file_category_year", "e_office_file", ["organisation_id", "category_id", "year"])
    op.create_index("ix_e_office_file_holder_file_id", "e_office_file_holder", ["file_id"])
    op.create_index("ix_e_office_file_holder_user_id", "e_office_file_holder", ["user_id"])
    op.create_index("ix_e_office_note_file_id", "e_office_note", ["file_id"])
    op.create_index("ix_e_office_attachment_file_id", "e_office_attachment", ["file_id"])
    op.create_index("ix_e_office_movement_file_id", "e_office_movement", ["file_id"])
    op.create_index("ix_e_office_movement_from_user_id", "e_office_movement", ["from_user_id"])
    op.create_index("ix_e_office_receipt_send_to_user_id", "e_office_receipt", ["send_to_user_id"])
    op.create_index("ix_e_office_receipt_status", "e_office_receipt", ["status"])
    op.create_index("ix_e_office_dispatch_file_id", "e_office_dispatch", ["file_id"])
    op.create_index("ix_e_office_dispatch_status", "e_office_dispatch", ["status"])
    op.create_index("ix_e_office_audit_entity", "e_office_audit_entry", ["organisation_id", "entity", "entity_id"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
