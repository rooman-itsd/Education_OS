"""Initial training-video-analysis schema: plans, drills, sessions and their attendees, videos (references and
metadata only), drill tags, annotations and the athletes they tag, the athlete-user links and the interim audit
entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy
(eos_core.rls.POLICY) through enable_rls().

Revision ID: tva_0001
Revises:
Create Date: 2026-10-30
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "tva_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "training_video_analysis_"
TABLES = (
    f"{P}plan",
    f"{P}drill",
    f"{P}session",
    f"{P}session_attendee",
    f"{P}video",
    f"{P}drill_tag",
    f"{P}annotation",
    f"{P}annotation_athlete",
    f"{P}athlete_link",
    f"{P}audit_entry",
)


def enable_rls(table: str) -> None:
    """tenant_isolation policy on app.organisation_id (Postgres only; SQLite scoping is in the repositories)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _base(created: bool = True, updated: bool = True) -> list[sa.Column]:
    cols = [
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
    ]
    if created:
        cols.append(sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
    if updated:
        cols.append(sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False))
    return cols


def _ref(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{P}{table}.id"), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}plan",
        *_base(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("coach_id", sa.String(36), nullable=False),
        sa.Column("squad_id", sa.String(36), nullable=True),
        sa.Column("start_date", sa.Date, nullable=False),
        sa.Column("end_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("objectives", sa.JSON, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}drill",
        *_base(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("intensity", sa.String(20), nullable=False),
        sa.Column("target_focus", sa.String(300), nullable=True),
        sa.Column("equipment_needed", sa.JSON, nullable=False),
        sa.Column("standard_duration_minutes", sa.Integer, nullable=True),
        sa.UniqueConstraint("organisation_id", "code", name="uq_training_video_analysis_drill_code"),
    )
    op.create_table(
        f"{P}session",
        *_base(),
        _ref("plan_id", "plan", nullable=True),
        sa.Column("coach_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("facility_id", sa.String(36), nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("scheduled_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("scheduled_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actual_duration_minutes", sa.Integer, nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("drill_ids", sa.JSON, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        f"{P}session_attendee",
        *_base(created=False, updated=False),
        _ref("session_id", "session"),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("session_id", "athlete_id", name="uq_training_video_analysis_session_attendee"),
    )
    op.create_table(
        f"{P}video",
        *_base(),
        _ref("session_id", "session", nullable=True),
        sa.Column("uploader_id", sa.String(36), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("video_url", sa.String(2000), nullable=False),
        sa.Column("thumbnail_url", sa.String(2000), nullable=True),
        sa.Column("duration_seconds", sa.Float, nullable=False),
        sa.Column("resolution", sa.String(20), nullable=True),
        sa.Column("recorded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("registered_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}drill_tag",
        *_base(updated=False),
        _ref("video_id", "video"),
        _ref("drill_id", "drill"),
        sa.Column("start_timestamp", sa.Float, nullable=False),
        sa.Column("end_timestamp", sa.Float, nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("tagged_by", sa.String(36), nullable=False),
    )
    op.create_table(
        f"{P}annotation",
        *_base(),
        _ref("video_id", "video"),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("start_timestamp", sa.Float, nullable=False),
        sa.Column("end_timestamp", sa.Float, nullable=True),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("drawing_markup", sa.JSON(none_as_null=True), nullable=True),
    )
    op.create_table(
        f"{P}annotation_athlete",
        *_base(created=False, updated=False),
        _ref("annotation_id", "annotation"),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("annotation_id", "athlete_id", name="uq_training_video_analysis_annotation_athlete"),
    )
    op.create_table(
        f"{P}athlete_link",
        *_base(created=False, updated=False),
        sa.Column("athlete_id", sa.String(36), nullable=False),
        sa.Column("user_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "athlete_id", name="uq_training_video_analysis_link_athlete"),
    )
    op.create_table(
        f"{P}audit_entry",
        *_base(created=False, updated=False),
        sa.Column("client_token", sa.String(120), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity_type", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("summary", sa.String(300), nullable=False),
        sa.Column("before", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("after", sa.JSON(none_as_null=True), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_training_video_analysis_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    for table, column in (
        (f"{P}plan", "coach_id"),
        (f"{P}plan", "status"),
        (f"{P}drill", "category"),
        (f"{P}session", "plan_id"),
        (f"{P}session", "coach_id"),
        (f"{P}session", "scheduled_start"),
        (f"{P}session", "status"),
        (f"{P}session_attendee", "athlete_id"),
        (f"{P}video", "session_id"),
        (f"{P}video", "uploader_id"),
        (f"{P}drill_tag", "video_id"),
        (f"{P}drill_tag", "drill_id"),
        (f"{P}annotation", "video_id"),
        (f"{P}annotation_athlete", "athlete_id"),
        (f"{P}athlete_link", "user_id"),
    ):
        op.create_index(f"ix_{table}_{column}", table, [column])
    op.create_index(
        "ix_training_video_analysis_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"]
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
