"""Initial government-portals schema: packages and their files.
Every table carries organisation_id; on Postgres each gets the forced tenant_isolation row-level-security policy.

Revision ID: gp_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "gp_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "government_portals_"
TABLES = ["package", "package_file"]
LIVE = sa.text("status != 'superseded'")


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}package",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("package_key", sa.String(100), nullable=False),
        sa.Column("form_code", sa.String(64), nullable=False),
        sa.Column("format_version", sa.String(20), nullable=False),
        sa.Column("period", sa.String(40), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("issues", sa.JSON, nullable=False),
        sa.Column("checklist", sa.JSON, nullable=False),
        sa.Column("caller_module", sa.String(60), nullable=True),
        sa.Column("caller_reference", sa.String(100), nullable=True),
        sa.Column("submitted_on", sa.Date, nullable=True),
        sa.Column("submitted_by", sa.String(36), nullable=True),
        sa.Column("portal_reference", sa.String(100), nullable=True),
        sa.Column("acknowledgement_document_id", sa.String(36), nullable=True),
        sa.Column("superseded_by", sa.String(36), nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        f"{P}package_file",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("package_id", sa.String(36), nullable=False),
        sa.Column("document_id", sa.String(36), nullable=False),
        sa.Column("filename", sa.String(200), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("metric", sa.String(40), nullable=True),
    )
    for table in TABLES:
        op.create_index(f"ix_{P}{table}_organisation_id", f"{P}{table}", ["organisation_id"])
    op.create_index(f"ix_{P}package_form_code", f"{P}package", ["form_code"])
    op.create_index(f"ix_{P}package_period", f"{P}package", ["period"])
    op.create_index(f"ix_{P}package_status", f"{P}package", ["status"])
    op.create_index(f"ix_{P}package_file_package_id", f"{P}package_file", ["package_id"])
    op.create_index(
        "uq_government_portals_package_live_key",
        f"{P}package",
        ["organisation_id", "package_key"],
        unique=True,
        sqlite_where=LIVE,
        postgresql_where=LIVE,
    )
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
