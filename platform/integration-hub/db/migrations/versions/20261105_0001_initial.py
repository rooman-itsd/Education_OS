"""Initial integration-hub schema: connections, credential references, account links, OAuth states, the delivery log
with its attempts, and inbound receipts. Every table carries organisation_id; on Postgres each gets the
tenant_isolation row-level-security policy (forced). No column holds a secret: credentials are references into the
secret store, and the few blobs kept for a while are AES-GCM encrypted.

Revision ID: integration_hub_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "integration_hub_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "integration_hub_connection",
    "integration_hub_connection_credential",
    "integration_hub_account_link",
    "integration_hub_oauth_state",
    "integration_hub_delivery",
    "integration_hub_delivery_attempt",
    "integration_hub_inbound_receipt",
]


def _ts(name: str, nullable: bool = True) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "integration_hub_connection",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("adapter", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("port", sa.String(64), nullable=False),
        sa.Column("mode", sa.String(10), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False),
        sa.Column("display_name", sa.String(120), nullable=True),
        sa.Column("settings", sa.JSON, nullable=False),
        sa.Column("connection_key_hash", sa.String(64), nullable=False),
        sa.Column("authorised", sa.Boolean, nullable=False),
        sa.Column("health_status", sa.String(20), nullable=False),
        sa.Column("health_detail", sa.String(500), nullable=True),
        _ts("health_checked_at"),
        _ts("expires_at"),
        _ts("health_window_start"),
        sa.Column("health_window_runs", sa.Integer, nullable=False),
        _ts("throttled_until"),
        sa.Column("disabled_reason", sa.String(500), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=True),
        _ts("created_at", nullable=False),
        _ts("updated_at", nullable=False),
        _ts("changed_at", nullable=False),
    )
    _enable_rls("integration_hub_connection")

    op.create_table(
        "integration_hub_connection_credential",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("integration_hub_connection.id"), nullable=False),
        sa.Column("name", sa.String(64), nullable=False),
        sa.Column("secret_ref", sa.String(300), nullable=False),
        sa.Column("fingerprint", sa.String(8), nullable=False),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("set_by", sa.String(36), nullable=True),
        _ts("set_at", nullable=False),
        _ts("expires_at"),
        sa.UniqueConstraint("connection_id", "name", name="uq_integration_hub_credential_name"),
    )
    _enable_rls("integration_hub_connection_credential")

    op.create_table(
        "integration_hub_account_link",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("connection_id", sa.String(36), sa.ForeignKey("integration_hub_connection.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("port", sa.String(64), nullable=False),
        sa.Column("provider", sa.String(64), nullable=False),
        sa.Column("provider_subject", sa.String(200), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("purpose", sa.String(200), nullable=True),
        sa.Column("granted_scopes", sa.JSON, nullable=False),
        sa.Column("secret_ref", sa.String(300), nullable=True),
        _ts("linked_at"),
        _ts("expires_at"),
        _ts("last_synced_at"),
        _ts("revoked_at"),
        sa.Column("revoke_cause", sa.String(40), nullable=True),
        _ts("created_at", nullable=False),
    )
    _enable_rls("integration_hub_account_link")

    op.create_table(
        "integration_hub_oauth_state",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("state_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("adapter", sa.String(64), nullable=False),
        sa.Column("connection_id", sa.String(36), nullable=False),
        sa.Column("account_link_id", sa.String(36), nullable=True),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("browser_binding_hash", sa.String(64), nullable=False),
        sa.Column("code_verifier_encrypted", sa.LargeBinary, nullable=False),
        sa.Column("return_url", sa.String(2048), nullable=False),
        _ts("expires_at", nullable=False),
        _ts("used_at"),
        _ts("created_at", nullable=False),
    )
    _enable_rls("integration_hub_oauth_state")

    op.create_table(
        "integration_hub_delivery",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("connection_id", sa.String(36), nullable=True),
        sa.Column("account_link_id", sa.String(36), nullable=True),
        sa.Column("port", sa.String(64), nullable=False),
        sa.Column("operation", sa.String(80), nullable=False),
        sa.Column("sync", sa.Boolean, nullable=False),
        sa.Column("mode", sa.String(10), nullable=True),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("caller_module", sa.String(64), nullable=True),
        sa.Column("caller_reference", sa.String(200), nullable=True),
        sa.Column("idempotency_key", sa.String(200), nullable=True),
        sa.Column("subject_key", sa.String(200), nullable=True),
        sa.Column("object_id", sa.String(64), nullable=True),
        sa.Column("person_id", sa.String(36), nullable=True),
        sa.Column("refs", sa.JSON, nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False),
        _ts("next_attempt_at"),
        sa.Column("last_error_code", sa.String(40), nullable=True),
        sa.Column("provider_reference", sa.String(200), nullable=True),
        sa.Column("payload_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("inbound_receipt_id", sa.String(36), nullable=True),
        _ts("created_at", nullable=False),
        _ts("started_at"),
        _ts("completed_at"),
    )
    _enable_rls("integration_hub_delivery")

    op.create_table(
        "integration_hub_delivery_attempt",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("delivery_id", sa.String(36), sa.ForeignKey("integration_hub_delivery.id"), nullable=False),
        sa.Column("attempt", sa.Integer, nullable=False),
        _ts("started_at", nullable=False),
        sa.Column("duration_ms", sa.Integer, nullable=False),
        sa.Column("outcome", sa.String(10), nullable=False),
        sa.Column("error_code", sa.String(40), nullable=True),
        sa.Column("provider_code", sa.String(40), nullable=True),
    )
    _enable_rls("integration_hub_delivery_attempt")

    # organisation_id is null until verify_inbound names the connection; such a row is visible to the platform role
    # (app.bypass_rls) only, which is the role that writes it.
    op.create_table(
        "integration_hub_inbound_receipt",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("adapter", sa.String(64), nullable=False),
        sa.Column("connection_id", sa.String(36), nullable=True),
        sa.Column("channel", sa.String(41), nullable=True),
        sa.Column("dedupe_key", sa.String(200), nullable=True),
        sa.Column("verdict", sa.String(12), nullable=False),
        sa.Column("source", sa.String(80), nullable=True),
        _ts("window_start"),
        sa.Column("rejected_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("raw_encrypted", sa.LargeBinary, nullable=True),
        _ts("received_at", nullable=False),
        _ts("processed_at"),
        sa.Column("note", sa.Text, nullable=True),
        # per connection: two organisations' connections at one provider may see the same event id
        sa.UniqueConstraint("connection_id", "dedupe_key", name="uq_integration_hub_inbound_dedupe"),
        # rejected requests: one counting row per source and minute
        sa.UniqueConstraint("adapter", "source", "window_start", name="uq_integration_hub_inbound_rejected_window"),
    )
    _enable_rls("integration_hub_inbound_receipt")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index(
        "ix_integration_hub_connection_port",
        "integration_hub_connection",
        ["organisation_id", "port", "provider", "enabled"],
    )
    op.create_index(
        "ix_integration_hub_connection_key", "integration_hub_connection", ["connection_key_hash"], unique=True
    )
    op.create_index(
        "ix_integration_hub_connection_credential_connection_id",
        "integration_hub_connection_credential",
        ["connection_id"],
    )
    op.create_index("ix_integration_hub_account_link_connection_id", "integration_hub_account_link", ["connection_id"])
    op.create_index(
        "ix_integration_hub_link_person", "integration_hub_account_link", ["organisation_id", "person_id", "status"]
    )
    op.create_index("ix_integration_hub_link_subject", "integration_hub_account_link", ["provider", "provider_subject"])
    op.create_index("ix_integration_hub_delivery_connection_id", "integration_hub_delivery", ["connection_id"])
    op.create_index(
        "ix_integration_hub_delivery_listing", "integration_hub_delivery", ["organisation_id", "created_at"]
    )
    op.create_index("ix_integration_hub_delivery_due", "integration_hub_delivery", ["status", "next_attempt_at"])
    op.create_index(
        "ix_integration_hub_delivery_idempotency",
        "integration_hub_delivery",
        ["organisation_id", "caller_module", "idempotency_key"],
    )
    op.create_index(
        "ix_integration_hub_delivery_subject", "integration_hub_delivery", ["organisation_id", "port", "subject_key"]
    )
    op.create_index(
        "ix_integration_hub_delivery_object", "integration_hub_delivery", ["organisation_id", "port", "object_id"]
    )
    op.create_index(
        "ix_integration_hub_delivery_attempt_delivery_id", "integration_hub_delivery_attempt", ["delivery_id"]
    )
    op.create_index("ix_integration_hub_inbound_received", "integration_hub_inbound_receipt", ["received_at"])


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
