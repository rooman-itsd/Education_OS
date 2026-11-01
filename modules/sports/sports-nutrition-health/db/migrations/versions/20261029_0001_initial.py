"""Initial sports-nutrition-health schema: nutrition plans and reviews, health records, injuries, appointments, the
athlete-to-user links learnt from athlete-performance and the interim audit entries. Every table carries
organisation_id; on Postgres each gets the tenant_isolation row-level-security policy (eos_core.rls.POLICY).

Revision ID: snh_0001
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "snh_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "sports_nutrition_health_"
TABLES = (
    f"{P}plan",
    f"{P}plan_review",
    f"{P}health_record",
    f"{P}injury",
    f"{P}appointment",
    f"{P}athlete_link",
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


def upgrade() -> None:
    op.create_table(
        f"{P}plan",
        *_base(),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("goal", sa.String(20), nullable=False),
        sa.Column("daily_calories", sa.Integer, nullable=True),
        sa.Column("protein_g", sa.Float, nullable=True),
        sa.Column("carbohydrate_g", sa.Float, nullable=True),
        sa.Column("fat_g", sa.Float, nullable=True),
        sa.Column("meals", sa.JSON, nullable=False),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=True),
        sa.Column("review_due_on", sa.Date, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("nutritionist_id", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}plan_review",
        *_base(),
        sa.Column("plan_id", sa.String(36), sa.ForeignKey(f"{P}plan.id"), nullable=False),
        sa.Column("reviewed_on", sa.Date, nullable=False),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("body_weight_kg", sa.Float, nullable=True),
        sa.Column("next_review_on", sa.Date, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("reviewed_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}health_record",
        *_base(),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("record_type", sa.String(20), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("details", sa.Text, nullable=True),
        sa.Column("recorded_on", sa.Date, nullable=False),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}injury",
        *_base(),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("body_part", sa.String(120), nullable=False),
        sa.Column("injury_type", sa.String(120), nullable=True),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("occurred_on", sa.Date, nullable=False),
        sa.Column("context", sa.String(20), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("expected_return_on", sa.Date, nullable=True),
        sa.Column("resolved_on", sa.Date, nullable=True),
        sa.Column("clinical_notes", sa.Text, nullable=True),
        sa.Column("reported_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}appointment",
        *_base(),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("practitioner_id", sa.String(36), nullable=False),
        sa.Column("appointment_type", sa.String(20), nullable=False),
        sa.Column("injury_id", sa.String(36), sa.ForeignKey(f"{P}injury.id"), nullable=True),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        f"{P}athlete_link",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "athlete_id", name="uq_sports_nutrition_health_link_athlete"),
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
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_sports_nutrition_health_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    for table, column in (
        (f"{P}plan", "athlete_id"),
        (f"{P}plan", "review_due_on"),
        (f"{P}plan", "status"),
        (f"{P}plan_review", "plan_id"),
        (f"{P}health_record", "athlete_id"),
        (f"{P}injury", "athlete_id"),
        (f"{P}injury", "status"),
        (f"{P}appointment", "athlete_id"),
        (f"{P}appointment", "practitioner_id"),
        (f"{P}athlete_link", "user_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_sports_nutrition_health_appointment_time", f"{P}appointment", ["organisation_id", "scheduled_at"]
    )
    op.create_index(
        "ix_sports_nutrition_health_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"]
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
