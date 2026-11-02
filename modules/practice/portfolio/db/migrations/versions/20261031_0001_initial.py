"""Initial portfolio schema: item types, items, item media, and reviews.
Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: portfolio_0001
Revises:
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "portfolio_0001"
down_revision = None
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "portfolio_item_type",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _ts("created_at"),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("requires_review", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("reviewer_person_ids", sa.JSON, nullable=False),
        sa.UniqueConstraint("organisation_id", "name", name="uq_portfolio_item_type_org_name"),
    )

    op.create_table(
        "portfolio_item",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("type_id", sa.String(36), sa.ForeignKey("portfolio_item_type.id"), nullable=False),
        sa.Column("owner_person_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=False),
        sa.Column("attributes", sa.JSON, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        _ts("submitted_at", nullable=True),
        _ts("decided_at", nullable=True),
        _ts("created_at"),
        _ts("updated_at"),
    )

    op.create_table(
        "portfolio_item_media",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("portfolio_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("document_id", sa.String(100), nullable=False),
        sa.Column("caption", sa.String(300), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("uploaded_by", sa.String(36), nullable=False),
        _ts("uploaded_at"),
    )

    op.create_table(
        "portfolio_review",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("item_id", sa.String(36), sa.ForeignKey("portfolio_item.id", ondelete="CASCADE"), nullable=False),
        sa.Column("reviewer_person_id", sa.String(36), nullable=False),
        sa.Column("decision", sa.String(30), nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        _ts("reviewed_at"),
    )

    op.create_index("ix_portfolio_item_type_organisation_id", "portfolio_item_type", ["organisation_id"])
    op.create_index("ix_portfolio_item_organisation_id", "portfolio_item", ["organisation_id"])
    op.create_index("ix_portfolio_item_media_organisation_id", "portfolio_item_media", ["organisation_id"])
    op.create_index("ix_portfolio_review_organisation_id", "portfolio_review", ["organisation_id"])

    op.create_index("ix_portfolio_item_owner", "portfolio_item", ["organisation_id", "owner_person_id"])
    op.create_index("ix_portfolio_item_type_id", "portfolio_item", ["type_id"])
    op.create_index("ix_portfolio_item_status", "portfolio_item", ["status"])
    op.create_index("ix_portfolio_item_media_item_id", "portfolio_item_media", ["item_id"])
    op.create_index("ix_portfolio_review_item_id", "portfolio_review", ["item_id"])

    # One literal call per table: tools/scripts/check-migrations.py looks for each table name in an rls call.
    _enable_rls("portfolio_item_type")
    _enable_rls("portfolio_item")
    _enable_rls("portfolio_item_media")
    _enable_rls("portfolio_review")


def downgrade() -> None:
    op.drop_table("portfolio_review")
    op.drop_table("portfolio_item_media")
    op.drop_table("portfolio_item")
    op.drop_table("portfolio_item_type")
