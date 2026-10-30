"""Initial athlete-performance schema: disciplines, metrics, athletes, results, fitness tests, assessments,
benchmarks, clearances and the interim audit entries. Every table carries organisation_id; on Postgres each gets the
tenant_isolation row-level-security policy (eos_core.rls.POLICY) through enable_rls().

Revision ID: ap_0001
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ap_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "athlete_performance_"
TABLES = (
    f"{P}discipline",
    f"{P}metric",
    f"{P}athlete",
    f"{P}result",
    f"{P}fitness_test",
    f"{P}assessment",
    f"{P}benchmark",
    f"{P}clearance",
    f"{P}audit_entry",
)


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _base(created: bool = True) -> list[sa.Column]:
    cols = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
    ]
    if created:
        cols.append(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    cols.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    return cols


def _ref(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{P}{table}.id"), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}discipline",
        *_base(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.UniqueConstraint("organisation_id", "name", name="uq_athlete_performance_discipline_name"),
    )
    op.create_table(
        f"{P}metric",
        *_base(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("unit", sa.String(30), nullable=False),
        sa.Column("direction", sa.String(20), nullable=False),
        _ref("discipline_id", "discipline", nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.UniqueConstraint("organisation_id", "name", name="uq_athlete_performance_metric_name"),
    )
    op.create_table(
        f"{P}athlete",
        *_base(),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("student_id", sa.String(36), nullable=True),
        sa.Column("full_name", sa.String(200), nullable=False),
        sa.Column("date_of_birth", sa.Date, nullable=True),
        sa.Column("gender", sa.String(20), nullable=True),
        _ref("primary_discipline_id", "discipline"),
        sa.Column("discipline_ids", sa.JSON, nullable=False),
        sa.Column("coach_id", sa.String(36), nullable=True),
        sa.Column("squad", sa.String(120), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("organisation_id", "user_id", name="uq_athlete_performance_athlete_user"),
    )
    op.create_table(
        f"{P}result",
        *_base(),
        _ref("athlete_id", "athlete"),
        _ref("metric_id", "metric"),
        sa.Column("value", sa.Float, nullable=False),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("context", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}fitness_test",
        *_base(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("metric_ids", sa.JSON, nullable=False),
        _ref("discipline_id", "discipline", nullable=True),
        sa.UniqueConstraint("organisation_id", "name", name="uq_athlete_performance_fitness_test_name"),
    )
    op.create_table(
        f"{P}assessment",
        *_base(),
        _ref("athlete_id", "athlete"),
        _ref("fitness_test_id", "fitness_test"),
        sa.Column("assessed_on", sa.Date, nullable=False),
        sa.Column("measurements", sa.JSON, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("assessor_id", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}benchmark",
        *_base(),
        _ref("metric_id", "metric"),
        _ref("discipline_id", "discipline", nullable=True),
        sa.Column("level", sa.String(60), nullable=False),
        sa.Column("gender", sa.String(10), nullable=True),
        sa.Column("age_group", sa.String(30), nullable=True),
        sa.Column("target_value", sa.Float, nullable=False),
        sa.Column("source", sa.String(300), nullable=True),
    )
    op.create_table(
        f"{P}clearance",
        *_base(created=False),
        _ref("athlete_id", "athlete"),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("valid_until", sa.Date, nullable=True),
        sa.Column("restrictions", sa.Text, nullable=True),
        sa.Column("set_by", sa.String(36), nullable=False),
        sa.Column("set_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "athlete_id", name="uq_athlete_performance_clearance_athlete"),
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
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_athlete_performance_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    for table, column in (
        (f"{P}metric", "discipline_id"),
        (f"{P}athlete", "primary_discipline_id"),
        (f"{P}athlete", "coach_id"),
        (f"{P}athlete", "status"),
        (f"{P}result", "metric_id"),
        (f"{P}assessment", "athlete_id"),
        (f"{P}assessment", "fitness_test_id"),
        (f"{P}benchmark", "metric_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_athlete_performance_result_athlete_metric", f"{P}result", ["athlete_id", "metric_id", "recorded_at"]
    )
    op.create_index(
        "ix_athlete_performance_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"]
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
