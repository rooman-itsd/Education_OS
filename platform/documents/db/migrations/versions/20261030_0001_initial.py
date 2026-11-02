"""Initial documents schema: document metadata, storage paths, status, and RLS.

Revision ID: documents_0001
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "documents_0001"
down_revision = None
branch_labels = None
depends_on = None

DOCUMENTS = "documents_document"


def enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        DOCUMENTS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("filename", sa.String(255), nullable=False),
        sa.Column("mime_type", sa.String(128), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("storage_path", sa.String(512), nullable=False),
        sa.Column("bucket", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="pending_upload"),
        sa.Column("entity_type", sa.String(64), nullable=True),
        sa.Column("entity_id", sa.String(64), nullable=True),
        sa.Column("uploaded_by", sa.String(36), nullable=False),
        sa.Column("client_token", sa.String(120), nullable=True),
        sa.Column("tags", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_documents_document_organisation_id", DOCUMENTS, ["organisation_id"])
    op.create_index("ix_documents_document_org_status", DOCUMENTS, ["organisation_id", "status"])
    op.create_index("ix_documents_document_org_entity", DOCUMENTS, ["organisation_id", "entity_type", "entity_id"])
    op.create_index(
        "uq_documents_document_org_token", DOCUMENTS, ["organisation_id", "uploaded_by", "client_token"], unique=True
    )
    enable_rls(DOCUMENTS)


def downgrade() -> None:
    op.drop_table(DOCUMENTS)
