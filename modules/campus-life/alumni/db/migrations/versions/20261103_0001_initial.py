"""Initial alumni schema: the directory, mentoring assignments, mentoring sessions and the audit trail. Every table
carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy. A partial unique index
keeps one active assignment per (organisation_id, student_id).

Revision ID: alumni_0001
Revises:
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "alumni_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "alumni_alumnus",
    "alumni_mentoring_assignment",
    "alumni_mentoring_session",
    "alumni_audit_entry",
]
ACTIVE_ONLY = sa.text("status = 'active'")


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "alumni_alumnus",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("graduation_year", sa.Integer, nullable=False),
        sa.Column("programme", sa.String(200), nullable=True),
        sa.Column("current_company", sa.String(200), nullable=True),
        sa.Column("current_designation", sa.String(200), nullable=True),
        sa.Column("industry", sa.String(200), nullable=True),
        sa.Column("city", sa.String(200), nullable=True),
        sa.Column("email", sa.String(200), nullable=True),
        sa.Column("phone", sa.String(200), nullable=True),
        sa.Column("linkedin_url", sa.String(200), nullable=True),
        sa.Column("is_mentor", sa.Boolean, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.Column("verified_by", sa.String(36), nullable=True),
        _ts("verified_at", nullable=True),
        _ts("archived_at", nullable=True),
        sa.Column("archive_reason", sa.Text, nullable=True),
    )
    _enable_rls("alumni_alumnus")

    op.create_table(
        "alumni_mentoring_assignment",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("mentor_id", sa.String(36), sa.ForeignKey("alumni_alumnus.id"), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("student_name", sa.String(200), nullable=True),
        sa.Column("started_on", sa.Date, nullable=False),
        sa.Column("ended_on", sa.Date, nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("focus", sa.String(200), nullable=True),
        sa.Column("assigned_by", sa.String(36), nullable=False),
        sa.Column("end_reason", sa.Text, nullable=True),
    )
    _enable_rls("alumni_mentoring_assignment")

    op.create_table(
        "alumni_mentoring_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("assignment_id", sa.String(36), sa.ForeignKey("alumni_mentoring_assignment.id"), nullable=False),
        _ts("scheduled_at"),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("location", sa.String(500), nullable=True),
        sa.Column("topic", sa.String(200), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
    )
    _enable_rls("alumni_mentoring_session")

    op.create_table(
        "alumni_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )
    _enable_rls("alumni_audit_entry")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_alumni_alumnus_listing", "alumni_alumnus", ["organisation_id", "status", "created_at"])
    op.create_index("ix_alumni_mentoring_assignment_mentor_id", "alumni_mentoring_assignment", ["mentor_id"])
    op.create_index("ix_alumni_mentoring_assignment_status", "alumni_mentoring_assignment", ["status"])
    op.create_index("ix_alumni_assignment_student", "alumni_mentoring_assignment", ["organisation_id", "student_id"])
    op.create_index(
        "uq_alumni_assignment_active_student",
        "alumni_mentoring_assignment",
        ["organisation_id", "student_id"],
        unique=True,
        postgresql_where=ACTIVE_ONLY,
        sqlite_where=ACTIVE_ONLY,
    )
    op.create_index("ix_alumni_session_assignment_time", "alumni_mentoring_session", ["assignment_id", "scheduled_at"])
    op.create_index("ix_alumni_audit_entity", "alumni_audit_entry", ["organisation_id", "entity", "entity_id"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
