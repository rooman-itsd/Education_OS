"""Initial search schema: reindex jobs, index state, the entitlement copy and dead letters. Every table carries
organisation_id NOT NULL (with a non-empty check) and, on Postgres, the forced tenant_isolation row-level security
policy.

Revision ID: search_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "search_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ("search_reindex_job", "search_index_state", "search_entitlement", "search_dead_letter")


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per transaction (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=False)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "search_reindex_job",
        _id(),
        _org(),
        _created(),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("type", sa.String(130), nullable=True),
        sa.Column("scope_key", sa.String(200), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("requested_by", sa.String(36), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("documents_indexed", sa.Integer, nullable=False),
        sa.Column("documents_failed", sa.Integer, nullable=False),
        sa.Column("error", sa.String(300), nullable=True),
        sa.CheckConstraint("organisation_id <> ''", name="ck_search_reindex_job_org_nonempty"),
    )
    op.create_index("ix_search_reindex_job_organisation_id", "search_reindex_job", ["organisation_id"])
    op.create_index("ix_search_reindex_job_listing", "search_reindex_job", ["organisation_id", "requested_at"])
    op.create_index(
        "uq_search_reindex_job_active",
        "search_reindex_job",
        ["organisation_id", "scope_key"],
        unique=True,
        postgresql_where=sa.text("status IN ('queued', 'running')"),
        sqlite_where=sa.text("status IN ('queued', 'running')"),
    )
    enable_rls("search_reindex_job")

    op.create_table(
        "search_index_state",
        _id(),
        _org(),
        _created(),
        sa.Column("type_key", sa.String(130), nullable=False),
        sa.Column("last_indexed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_reindex_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "type_key", name="uq_search_index_state_org_type"),
        sa.CheckConstraint("organisation_id <> ''", name="ck_search_index_state_org_nonempty"),
    )
    op.create_index("ix_search_index_state_organisation_id", "search_index_state", ["organisation_id"])
    enable_rls("search_index_state")

    op.create_table(
        "search_entitlement",
        _id(),
        _org(),
        _created(),
        sa.Column("modules", sa.JSON, nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", name="uq_search_entitlement_org"),
        sa.CheckConstraint("organisation_id <> ''", name="ck_search_entitlement_org_nonempty"),
    )
    op.create_index("ix_search_entitlement_organisation_id", "search_entitlement", ["organisation_id"])
    enable_rls("search_entitlement")

    op.create_table(
        "search_dead_letter",
        _id(),
        _org(),
        _created(),
        sa.Column("module", sa.String(64), nullable=False),
        sa.Column("type_key", sa.String(130), nullable=False),
        sa.Column("record_id", sa.String(128), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=True),
        sa.Column("reason", sa.String(60), nullable=False),
        sa.UniqueConstraint("organisation_id", "type_key", "record_id", name="uq_search_dead_letter_record"),
        sa.CheckConstraint("organisation_id <> ''", name="ck_search_dead_letter_org_nonempty"),
    )
    op.create_index("ix_search_dead_letter_organisation_id", "search_dead_letter", ["organisation_id"])
    enable_rls("search_dead_letter")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
