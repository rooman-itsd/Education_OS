"""Initial skill-progress schema: frameworks, skills, rubrics, assessments and the interim audit entries. Every table
carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy (eos_core.rls.POLICY)
through enable_rls().

Revision ID: sp_0001
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "sp_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "skill_progress_"
TABLES = (
    f"{P}framework",
    f"{P}skill",
    f"{P}rubric",
    f"{P}assessment",
    f"{P}audit_entry",
)


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _base() -> list[sa.Column]:
    return [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    ]


def _ref(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{P}{table}.id"), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}framework",
        *_base(),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_skill_progress_framework_code"),
    )
    op.create_table(
        f"{P}skill",
        *_base(),
        _ref("framework_id", "framework"),
        _ref("parent_skill_id", "skill", nullable=True),
        sa.Column("code", sa.String(60), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(120), nullable=True),
        sa.Column("level_scale", sa.JSON, nullable=False),
        sa.UniqueConstraint("organisation_id", "framework_id", "code", name="uq_skill_progress_skill_code"),
    )
    op.create_table(
        f"{P}rubric",
        *_base(),
        _ref("skill_id", "skill", nullable=True),
        _ref("framework_id", "framework", nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("criteria", sa.JSON, nullable=False),
    )
    op.create_table(
        f"{P}assessment",
        *_base(),
        sa.Column("learner_id", sa.String(36), nullable=False),
        sa.Column("evaluator_id", sa.String(36), nullable=False),
        _ref("skill_id", "skill"),
        _ref("rubric_id", "rubric"),
        sa.Column("assessed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("criterion_scores", sa.JSON, nullable=False),
        sa.Column("overall_score", sa.Float, nullable=False),
        sa.Column("level_achieved", sa.String(120), nullable=False),
        sa.Column("level_key", sa.String(60), nullable=False),
        sa.Column("level_rank", sa.Integer, nullable=False),
        sa.Column("top_level", sa.Boolean, nullable=False),
        sa.Column("feedback", sa.Text, nullable=True),
        sa.Column("evidence_urls", sa.JSON, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("recorded_by", sa.String(36), nullable=False),
        sa.Column("verified_by", sa.String(36), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_by", sa.String(36), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        f"{P}audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("client_token", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("before", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("after", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_skill_progress_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    for table, column in (
        (f"{P}framework", "status"),
        (f"{P}skill", "framework_id"),
        (f"{P}skill", "parent_skill_id"),
        (f"{P}rubric", "skill_id"),
        (f"{P}rubric", "framework_id"),
        (f"{P}assessment", "evaluator_id"),
        (f"{P}assessment", "skill_id"),
        (f"{P}assessment", "rubric_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_skill_progress_assessment_learner",
        f"{P}assessment",
        ["organisation_id", "learner_id", "skill_id", "assessed_at"],
    )
    op.create_index(
        "ix_skill_progress_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"]
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
