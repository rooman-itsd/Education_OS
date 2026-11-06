"""Initial video-conferencing schema: meetings, attendance, recordings, Graph subscriptions, the Zoom per-host quota and
the audit trail. Every table carries organisation_id; on Postgres each gets the forced tenant_isolation policy.

Revision ID: vc_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "vc_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "video_conferencing_"
TABLES = ["meeting", "attendance", "recording", "graph_subscription", "host_quota", "audit_entry"]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}meeting",
        _id(),
        _org(),
        _ts("created_at"),
        sa.Column("connection_id", sa.String(36), nullable=False),
        sa.Column("meeting_key", sa.String(128), nullable=False),
        sa.Column("caller_module", sa.String(60), nullable=True),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_meeting_id", sa.String(256), nullable=True),
        sa.Column("provider_instance_id", sa.String(256), nullable=True),
        sa.Column("host_user_id", sa.String(256), nullable=True),
        sa.Column("room_name", sa.String(120), nullable=True),
        sa.Column("status", sa.String(12), nullable=False),
        _ts("starts_at"),
        sa.Column("duration_minutes", sa.Integer, nullable=False),
        _ts("started_at", True),
        _ts("ended_at", True),
        sa.Column("join_url", sa.Text, nullable=True),
        sa.Column("host_join_url", sa.Text, nullable=True),
        sa.Column("passcode", sa.Text, nullable=True),
        _ts("attendance_fetched_at", True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "meeting_key", name="uq_video_conferencing_meeting_key"),
    )
    op.create_table(
        f"{P}attendance",
        _id(),
        _org(),
        sa.Column("meeting_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("display_name", sa.String(200), nullable=True),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("total_seconds", sa.Integer, nullable=False),
        sa.Column("intervals", sa.JSON, nullable=False),
        sa.Column("complete", sa.Boolean, nullable=False),
    )
    op.create_table(
        f"{P}recording",
        _id(),
        _org(),
        sa.Column("meeting_id", sa.String(36), nullable=False),
        sa.Column("provider_recording_id", sa.String(256), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        _ts("started_at", True),
        _ts("ended_at", True),
        sa.Column("bytes", sa.BigInteger, nullable=True),
        _ts("expires_at", True),
        sa.Column("document_id", sa.String(36), nullable=True),
        sa.Column("sha256", sa.String(64), nullable=True),
        sa.UniqueConstraint("meeting_id", "provider_recording_id", name="uq_video_conferencing_recording"),
    )
    op.create_table(
        f"{P}graph_subscription",
        _id(),
        _org(),
        sa.Column("connection_id", sa.String(36), nullable=False),
        sa.Column("subscription_id", sa.String(128), nullable=False),
        sa.Column("resource", sa.String(300), nullable=False),
        sa.Column("client_state_ref", sa.String(64), nullable=False),
        _ts("expires_at"),
    )
    op.create_table(
        f"{P}host_quota",
        _id(),
        _org(),
        sa.Column("connection_id", sa.String(36), nullable=False),
        sa.Column("host_user_id", sa.String(256), nullable=False),
        sa.Column("day", sa.Date, nullable=False),
        sa.Column("calls", sa.Integer, nullable=False),
        sa.UniqueConstraint(
            "organisation_id", "connection_id", "host_user_id", "day", name="uq_video_conferencing_quota"
        ),
    )
    op.create_table(
        f"{P}audit_entry",
        _id(),
        _org(),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )
    for table in TABLES:
        op.create_index(f"ix_{P}{table}_organisation_id", f"{P}{table}", ["organisation_id"])
    op.create_index(f"ix_{P}meeting_connection_id", f"{P}meeting", ["connection_id"])
    op.create_index("ix_video_conferencing_meeting_provider_ref", f"{P}meeting", ["provider", "provider_meeting_id"])
    op.create_index(f"ix_{P}attendance_meeting_id", f"{P}attendance", ["meeting_id"])
    op.create_index(f"ix_{P}recording_meeting_id", f"{P}recording", ["meeting_id"])
    op.create_index(f"ix_{P}graph_subscription_connection_id", f"{P}graph_subscription", ["connection_id"])
    op.create_index(f"ix_{P}graph_subscription_subscription_id", f"{P}graph_subscription", ["subscription_id"])
    op.create_index("ix_video_conferencing_audit_entity", f"{P}audit_entry", ["organisation_id", "entity", "entity_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
