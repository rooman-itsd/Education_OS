"""Initial nad schema: submissions, their upload files, lodged awards. Every table carries organisation_id; on
Postgres each gets the forced tenant_isolation row-level-security policy.

Revision ID: nad_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "nad_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "nad_"
TABLES = ["submission", "submission_file", "lodged_award"]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}submission",
        _id(),
        _org(),
        sa.Column("kind", sa.String(20), nullable=False),
        sa.Column("depository", sa.String(3), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("award_kind", sa.String(30), nullable=True),
        sa.Column("template_code", sa.String(60), nullable=True),
        sa.Column("programme_code", sa.String(40), nullable=True),
        sa.Column("session", sa.String(7), nullable=False),
        sa.Column("term", sa.String(30), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("rows", sa.Integer, nullable=False),
        sa.Column("accepted_rows", sa.Integer, nullable=True),
        sa.Column("rejected_rows", sa.Integer, nullable=True),
        sa.Column("caller_reference", sa.String(100), nullable=False),
        sa.Column("batch_key", sa.String(100), nullable=False),
        sa.Column("payload_digest", sa.String(64), nullable=False),
        sa.Column("reason", sa.String(300), nullable=True),
        sa.Column("steps", sa.JSON, nullable=False),
        sa.Column("row_errors", sa.JSON, nullable=False),
        sa.Column("portal_reference", sa.String(100), nullable=True),
        sa.Column("uploaded_on", sa.Date, nullable=True),
        sa.Column("uploaded_by", sa.String(36), nullable=True),
        sa.Column("acknowledgement_document_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "batch_key", name="uq_nad_submission_batch_key"),
    )
    op.create_table(
        f"{P}submission_file",
        _id(),
        _org(),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("rows", sa.Integer, nullable=False),
        sa.Column("template_version", sa.String(10), nullable=False),
    )
    op.create_table(
        f"{P}lodged_award",
        _id(),
        _org(),
        sa.Column("award_number", sa.String(60), nullable=False),
        sa.Column("award_kind", sa.String(30), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("apaar_id_hash", sa.String(64), nullable=False),
        sa.Column("submission_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        _ts("created_at"),
        sa.UniqueConstraint("organisation_id", "award_kind", "award_number", name="uq_nad_lodged_award"),
    )
    for table in TABLES:
        op.create_index(f"ix_{P}{table}_organisation_id", f"{P}{table}", ["organisation_id"])
    op.create_index(f"ix_{P}submission_kind", f"{P}submission", ["kind"])
    op.create_index(f"ix_{P}submission_session", f"{P}submission", ["session"])
    op.create_index(f"ix_{P}submission_status", f"{P}submission", ["status"])
    op.create_index(f"ix_{P}submission_created_at", f"{P}submission", ["created_at"])
    op.create_index(f"ix_{P}submission_file_submission_id", f"{P}submission_file", ["submission_id"])
    op.create_index(f"ix_{P}lodged_award_person_id", f"{P}lodged_award", ["person_id"])
    op.create_index(f"ix_{P}lodged_award_submission_id", f"{P}lodged_award", ["submission_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
