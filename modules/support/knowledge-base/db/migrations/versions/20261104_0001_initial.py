"""Initial knowledge-base schema: categories, articles, revisions, feedback, daily views, today's view keys and audit
entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: knowledge_base_0001
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "knowledge_base_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "knowledge_base_category",
    "knowledge_base_article",
    "knowledge_base_revision",
    "knowledge_base_feedback",
    "knowledge_base_view_day",
    "knowledge_base_view_seen",
    "knowledge_base_audit_entry",
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
        "knowledge_base_category",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("parent_id", sa.String(36), sa.ForeignKey("knowledge_base_category.id"), nullable=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "knowledge_base_article",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("slug", sa.String(120), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("review_by", sa.Date, nullable=True),
        sa.Column("published_revision_no", sa.Integer, nullable=True),
        sa.Column("open_revision_no", sa.Integer, nullable=True),
        sa.Column("last_revision_no", sa.Integer, nullable=False),
        sa.Column("view_count", sa.Integer, nullable=False),
        sa.Column("helpful_count", sa.Integer, nullable=False),
        sa.Column("not_helpful_count", sa.Integer, nullable=False),
        _ts("first_published_at", nullable=True),
        _ts("published_at", nullable=True),
        _ts("archived_at", nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "slug", name="uq_knowledge_base_article_slug"),
    )
    op.create_table(
        "knowledge_base_revision",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("knowledge_base_article.id"), nullable=False),
        sa.Column("revision_no", sa.Integer, nullable=False),
        sa.Column("state", sa.String(12), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.String(500), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("category_id", sa.String(36), nullable=False),
        sa.Column("tags", sa.JSON, nullable=False),
        sa.Column("audience", sa.String(10), nullable=False),
        sa.Column("related_article_ids", sa.JSON, nullable=False),
        sa.Column("refs", sa.JSON, nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("change_note", sa.String(500), nullable=True),
        _ts("submitted_at", nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=True),
        sa.Column("review_comment", sa.Text, nullable=True),
        _ts("published_at", nullable=True),
        sa.UniqueConstraint("article_id", "revision_no", name="uq_knowledge_base_revision_no"),
    )
    op.create_table(
        "knowledge_base_feedback",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("knowledge_base_article.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("helpful", sa.Boolean, nullable=False),
        sa.Column("comment", sa.Text, nullable=True),
        sa.Column("revision_no", sa.Integer, nullable=False),
        _created(),
        sa.UniqueConstraint("article_id", "person_id", name="uq_knowledge_base_feedback_person"),
    )
    op.create_table(
        "knowledge_base_view_day",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("knowledge_base_article.id"), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("views", sa.Integer, nullable=False),
        sa.UniqueConstraint("article_id", "day", name="uq_knowledge_base_view_day"),
    )
    op.create_table(
        "knowledge_base_view_seen",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("article_id", sa.String(36), sa.ForeignKey("knowledge_base_article.id"), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("reader_key", sa.String(64), nullable=False),
        sa.UniqueConstraint("article_id", "day", "reader_key", name="uq_knowledge_base_view_seen"),
    )
    op.create_table(
        "knowledge_base_audit_entry",
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
    op.create_index("ix_knowledge_base_category_parent", "knowledge_base_category", ["organisation_id", "parent_id"])
    op.create_index("ix_knowledge_base_article_status", "knowledge_base_article", ["organisation_id", "status"])
    op.create_index(
        "ix_knowledge_base_revision_category", "knowledge_base_revision", ["organisation_id", "category_id"]
    )
    op.create_index(
        "ix_knowledge_base_audit_entity", "knowledge_base_audit_entry", ["organisation_id", "entity", "entity_id"]
    )
    _enable_rls("knowledge_base_category")
    _enable_rls("knowledge_base_article")
    _enable_rls("knowledge_base_revision")
    _enable_rls("knowledge_base_feedback")
    _enable_rls("knowledge_base_view_day")
    _enable_rls("knowledge_base_view_seen")
    _enable_rls("knowledge_base_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
