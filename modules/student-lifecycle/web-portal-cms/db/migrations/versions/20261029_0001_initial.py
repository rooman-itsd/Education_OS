"""Initial web-portal-cms schema: each organisation's pages and announcements, and the audit trail. Every table
carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: web_portal_cms_0001
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "web_portal_cms_0001"
down_revision = None
branch_labels = None
depends_on = None


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "web_portal_cms_page",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("seo_description", sa.String(300), nullable=True),
        sa.Column("published", sa.Boolean, nullable=False),
        _ts("published_at", nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index("ix_web_portal_cms_page_organisation_id", "web_portal_cms_page", ["organisation_id"])
    op.create_index("uq_web_portal_cms_page_slug", "web_portal_cms_page", ["organisation_id", "slug"], unique=True)
    op.create_index(
        "ix_web_portal_cms_page_listing", "web_portal_cms_page", ["organisation_id", "published", "updated_at"]
    )

    op.create_table(
        "web_portal_cms_announcement",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        _ts("starts_at", nullable=True),
        _ts("ends_at", nullable=True),
        sa.Column("published", sa.Boolean, nullable=False),
        _ts("published_at", nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("updated_by", sa.String(36), nullable=False),
        _ts("created_at"),
        _ts("updated_at"),
    )
    op.create_index(
        "ix_web_portal_cms_announcement_organisation_id", "web_portal_cms_announcement", ["organisation_id"]
    )
    op.create_index(
        "ix_web_portal_cms_announcement_listing",
        "web_portal_cms_announcement",
        ["organisation_id", "published", "published_at"],
    )

    op.create_table(
        "web_portal_cms_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("detail", sa.JSON, nullable=True),
        _ts("occurred_at"),
    )
    op.create_index("ix_web_portal_cms_audit_entry_organisation_id", "web_portal_cms_audit_entry", ["organisation_id"])
    op.create_index("ix_web_portal_cms_audit_entry_entity", "web_portal_cms_audit_entry", ["entity", "entity_id"])

    # One literal call per table: tools/scripts/check-migrations.py looks for each table name in an rls call.
    _enable_rls("web_portal_cms_page")
    _enable_rls("web_portal_cms_announcement")
    _enable_rls("web_portal_cms_audit_entry")


def downgrade() -> None:
    op.drop_table("web_portal_cms_audit_entry")
    op.drop_table("web_portal_cms_announcement")
    op.drop_table("web_portal_cms_page")
