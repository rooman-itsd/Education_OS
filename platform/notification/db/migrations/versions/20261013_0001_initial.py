"""Initial notification schema: messages, organisation template overrides and recipient preferences. Every table
carries organisation_id NOT NULL (with a non-empty check) and, on Postgres, the tenant_isolation row-level
security policy.

Revision ID: notification_0001
Revises:
Create Date: 2026-10-13
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "notification_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = ("notification_message", "notification_template", "notification_preference")


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per transaction (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _updated() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False)


def upgrade() -> None:
    op.create_table(
        "notification_message",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _created(),
        sa.Column("template_key", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("recipient_id", sa.String(36), nullable=True),
        sa.Column("recipient_key", sa.String(254), nullable=False),
        sa.Column("recipient_address", sa.String(254), nullable=True),
        sa.Column("locale", sa.String(10), nullable=True),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("variables", sa.JSON, nullable=False),
        sa.Column("body", sa.Text, nullable=True),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column("client_token", sa.String(120), nullable=True),
        sa.Column("request_hash", sa.String(64), nullable=True),
        sa.Column("source_event_id", sa.String(36), nullable=True),
        sa.Column("attempts", sa.Integer, nullable=False),
        sa.Column("recovery_failures", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("last_recovery_error", sa.String(60), nullable=True),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("provider_message_id", sa.String(200), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        _updated(),
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_notification_message_org_token"),
        sa.UniqueConstraint(
            "organisation_id",
            "source_event_id",
            "template_key",
            "channel",
            "recipient_key",
            name="uq_notification_message_org_event",
        ),
        sa.CheckConstraint("organisation_id <> ''", name="ck_notification_message_org_nonempty"),
    )
    op.create_index("ix_notification_message_organisation_id", "notification_message", ["organisation_id"])
    op.create_index(
        "ix_notification_message_inbox", "notification_message", ["organisation_id", "recipient_id", "created_at"]
    )
    op.create_index(
        "ix_notification_message_status", "notification_message", ["organisation_id", "status", "created_at"]
    )
    op.create_index("ix_notification_message_dispatch", "notification_message", ["status", "next_attempt_at"])
    op.create_index("ix_notification_message_lease", "notification_message", ["status", "lease_expires_at"])
    enable_rls("notification_message")

    op.create_table(
        "notification_template",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _created(),
        sa.Column("key", sa.String(120), nullable=False),
        sa.Column("channel", sa.String(20), nullable=False),
        sa.Column("locale", sa.String(10), nullable=False),
        sa.Column("subject", sa.String(300), nullable=True),
        sa.Column("body", sa.Text, nullable=False),
        _updated(),
        sa.UniqueConstraint("organisation_id", "key", "channel", "locale", name="uq_notification_template_org_key"),
        sa.CheckConstraint("organisation_id <> ''", name="ck_notification_template_org_nonempty"),
    )
    op.create_index("ix_notification_template_organisation_id", "notification_template", ["organisation_id"])
    enable_rls("notification_template")

    op.create_table(
        "notification_preference",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        _created(),
        sa.Column("user_id", sa.String(36), nullable=False),
        sa.Column("locale", sa.String(10), nullable=True),
        sa.Column("channels", sa.JSON, nullable=False),
        sa.Column("quiet_hours", sa.JSON, nullable=True),
        _updated(),
        sa.UniqueConstraint("organisation_id", "user_id", name="uq_notification_preference_org_user"),
        sa.CheckConstraint("organisation_id <> ''", name="ck_notification_preference_org_nonempty"),
    )
    op.create_index("ix_notification_preference_organisation_id", "notification_preference", ["organisation_id"])
    enable_rls("notification_preference")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
