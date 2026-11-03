"""A separate upload key per document, and versions.

- upload_path: where the client PUTs while a document is pending. Confirm copies the validated object to
  storage_path (the document's own key) and deletes the upload, so a replayed or late PUT cannot change a
  confirmed file. Existing rows keep NULL: they uploaded to storage_path, which confirm still accepts.
- version (default 1), version_of (the first version's id) and superseded_by: every version is a row; the latest
  has superseded_by NULL, so every existing row is a first and latest version.

All additive and nullable (version has a server default), so upgrade is safe on a populated table.

Revision ID: documents_0002
Revises: documents_0001
Create Date: 2026-11-02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "documents_0002"
down_revision = "documents_0001"
branch_labels = None
depends_on = None

TABLE = "documents_document"


def upgrade() -> None:
    with op.batch_alter_table(TABLE) as batch:
        batch.add_column(sa.Column("upload_path", sa.String(512), nullable=True))
        batch.add_column(sa.Column("version", sa.Integer, nullable=False, server_default="1"))
        batch.add_column(sa.Column("version_of", sa.String(36), nullable=True))
        batch.add_column(sa.Column("superseded_by", sa.String(36), nullable=True))
    op.create_index("ix_documents_document_org_version_of", TABLE, ["organisation_id", "version_of"])


def downgrade() -> None:
    op.drop_index("ix_documents_document_org_version_of", table_name=TABLE)
    with op.batch_alter_table(TABLE) as batch:
        for column in ("superseded_by", "version_of", "version", "upload_path"):
            batch.drop_column(column)
