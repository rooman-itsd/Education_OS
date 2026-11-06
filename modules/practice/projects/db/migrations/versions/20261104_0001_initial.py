"""Initial projects schema: projects, team members, guides, milestones, submissions (milestone versions and final
submissions), reviews, audit entries. Every table carries organisation_id; on Postgres each gets the
tenant_isolation row-level-security policy.

Revision ID: projects_0001
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "projects_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "projects_project",
    "projects_member",
    "projects_guide",
    "projects_milestone",
    "projects_submission",
    "projects_review",
    "projects_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _ref(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "projects_project",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("kind", sa.String(100), nullable=True),
        sa.Column("academic_year", sa.String(20), nullable=True),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=False),
        sa.Column("external_partner", sa.String(200), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("outcome", sa.String(100), nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "projects_member",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ref("project_id", "projects_project"),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(10), nullable=False),
        _ts("joined_at"),
        _ts("left_at", nullable=True),
    )
    op.create_table(
        "projects_guide",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ref("project_id", "projects_project"),
        sa.Column("person_id", sa.String(36), nullable=False),
        _ts("assigned_at"),
        _ts("removed_at", nullable=True),
    )
    op.create_table(
        "projects_milestone",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        _ref("project_id", "projects_project"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("due_on", sa.Date, nullable=False),
        sa.Column("weight", sa.Float, nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        _ts("overdue_flagged_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "projects_submission",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ref("project_id", "projects_project"),
        _ref("milestone_id", "projects_milestone", nullable=True),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("note", sa.Text, nullable=False),
        sa.Column("document_ids", sa.JSON, nullable=False),
        sa.Column("submitted_by", sa.String(36), nullable=False),
        _ts("submitted_at"),
        sa.UniqueConstraint("organisation_id", "project_id", "milestone_id", "version", name="uq_projects_submission"),
    )
    op.create_table(
        "projects_review",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ref("submission_id", "projects_submission"),
        sa.Column("reviewer_id", sa.String(36), nullable=False),
        sa.Column("decision", sa.String(10), nullable=False),
        sa.Column("comments", sa.Text, nullable=True),
        sa.Column("score", sa.Float, nullable=True),
        _ts("reviewed_at"),
        sa.UniqueConstraint("organisation_id", "submission_id", name="uq_projects_review_submission"),
    )
    op.create_table(
        "projects_audit_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_projects_project_status", "projects_project", ["organisation_id", "status"])
    op.create_index("ix_projects_member_person", "projects_member", ["organisation_id", "person_id"])
    op.create_index("ix_projects_member_project", "projects_member", ["organisation_id", "project_id"])
    op.create_index("ix_projects_guide_person", "projects_guide", ["organisation_id", "person_id"])
    op.create_index("ix_projects_guide_project", "projects_guide", ["organisation_id", "project_id"])
    op.create_index("ix_projects_milestone_status", "projects_milestone", ["status"])
    op.create_index("ix_projects_milestone_project", "projects_milestone", ["organisation_id", "project_id", "due_on"])
    op.create_index("ix_projects_submission_project", "projects_submission", ["organisation_id", "project_id"])
    op.create_index("ix_projects_audit_entity", "projects_audit_entry", ["organisation_id", "entity", "entity_id"])

    _enable_rls("projects_project")
    _enable_rls("projects_member")
    _enable_rls("projects_guide")
    _enable_rls("projects_milestone")
    _enable_rls("projects_submission")
    _enable_rls("projects_review")
    _enable_rls("projects_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
