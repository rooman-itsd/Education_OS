"""Initial digilocker schema: issued documents, pull request log, issuance history. Every table carries
organisation_id; on Postgres each gets the forced tenant_isolation row-level-security policy.

Revision ID: dgl_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "dgl_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "digilocker_"
TABLES = ["issued_document", "pull_request_log", "issuance_history"]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}issued_document",
        _id(),
        _org(),
        sa.Column("issuance_key", sa.String(100), nullable=False),
        sa.Column("doc_kind", sa.String(40), nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=False),
        sa.Column("uri", sa.String(200), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("document_number", sa.String(60), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("holder_name_normalised", sa.String(200), nullable=False),
        sa.Column("holder_dob", sa.Date, nullable=True),
        sa.Column("search_key_hash", sa.String(64), nullable=False),
        sa.Column("wallet_account_id", sa.String(100), nullable=True),
        sa.Column("data_xml", sa.Text, nullable=True),
        sa.Column("push_pending", sa.String(1), nullable=True),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("issued_on", sa.Date, nullable=False),
        sa.Column("valid_from", sa.Date, nullable=True),
        sa.Column("valid_to", sa.Date, nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
        _ts("pushed_at", nullable=True),
        _ts("withdrawn_at", nullable=True),
        _ts("last_pulled_at", nullable=True),
        sa.UniqueConstraint("organisation_id", "issuance_key", name="uq_digilocker_doc_issuance_key"),
        sa.UniqueConstraint("organisation_id", "doc_kind", "document_number", name="uq_digilocker_doc_number"),
        sa.UniqueConstraint("organisation_id", "uri", name="uq_digilocker_doc_uri"),
    )
    op.create_table(
        f"{P}pull_request_log",
        _id(),
        _org(),
        sa.Column("txn", sa.String(100), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("doc_type", sa.String(40), nullable=True),
        sa.Column("matched", sa.Boolean, nullable=False),
        sa.Column("issued_document_id", sa.String(36), nullable=True),
        _ts("received_at"),
        sa.UniqueConstraint("organisation_id", "channel", "txn", name="uq_digilocker_pull_txn"),
    )
    op.create_table(
        f"{P}issuance_history",
        _id(),
        _org(),
        sa.Column("issued_document_id", sa.String(36), nullable=False),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("detail", sa.JSON, nullable=False),
        sa.Column("delivery_id", sa.String(36), nullable=True),
        _ts("occurred_at"),
    )
    for table in TABLES:
        op.create_index(f"ix_{P}{table}_organisation_id", f"{P}{table}", ["organisation_id"])
    op.create_index(f"ix_{P}issued_document_person_id", f"{P}issued_document", ["person_id"])
    op.create_index(f"ix_{P}issued_document_status", f"{P}issued_document", ["status"])
    op.create_index(f"ix_{P}issued_document_created_at", f"{P}issued_document", ["created_at"])
    op.create_index(
        "ix_digilocker_doc_lookup", f"{P}issued_document", ["organisation_id", "doc_type", "search_key_hash"]
    )
    op.create_index(f"ix_{P}pull_request_log_received_at", f"{P}pull_request_log", ["received_at"])
    op.create_index(f"ix_{P}issuance_history_issued_document_id", f"{P}issuance_history", ["issued_document_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
