"""Initial wearables schema: link state, normalised records, the read log and the audit trail. Every table carries
organisation_id; on Postgres each gets the forced tenant_isolation row-level-security policy.

Revision ID: wear_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "wear_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "wearables_"
TABLES = ["link_state", "record", "read_log", "audit_entry"]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def upgrade() -> None:
    op.create_table(
        f"{P}link_state",
        _id(),
        _org(),
        sa.Column("connection_id", sa.String(36), nullable=False),
        sa.Column("account_link_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("provider_subject", sa.String(128), nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        _ts("status_since"),
        sa.Column("data_types", sa.JSON, nullable=False),
        _ts("created_at"),
        _ts("last_synced_at", True),
        _ts("last_data_at", True),
        sa.Column("consecutive_failures", sa.Integer, nullable=False),
        _ts("failing_since", True),
        sa.Column("last_error_code", sa.String(30), nullable=True),
        sa.UniqueConstraint("organisation_id", "account_link_id", name="uq_wearables_link"),
    )
    op.create_table(
        f"{P}record",
        _id(),
        _org(),
        sa.Column("account_link_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("provider", sa.String(20), nullable=False),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("provider_record_id", sa.String(200), nullable=False),
        sa.Column("record_date", sa.Date, nullable=False),
        sa.Column("fields", sa.JSON, nullable=False),
        sa.Column("display_scope", sa.String(12), nullable=False),
        _ts("received_at"),
        sa.UniqueConstraint(
            "organisation_id", "account_link_id", "data_type", "provider_record_id", name="uq_wearables_record"
        ),
    )
    op.create_table(
        f"{P}read_log",
        _id(),
        _org(),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("caller_module", sa.String(60), nullable=True),
        sa.Column("purpose", sa.String(40), nullable=False),
        sa.Column("data_type", sa.String(30), nullable=False),
        sa.Column("date_from", sa.Date, nullable=False),
        sa.Column("date_to", sa.Date, nullable=False),
        _ts("read_at"),
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
    op.create_index("ix_wearables_link_subject", f"{P}link_state", ["provider", "provider_subject"])
    op.create_index("ix_wearables_link_person", f"{P}link_state", ["organisation_id", "person_id"])
    op.create_index(f"ix_{P}record_account_link_id", f"{P}record", ["account_link_id"])
    op.create_index(
        "ix_wearables_record_read", f"{P}record", ["organisation_id", "person_id", "data_type", "record_date"]
    )
    op.create_index("ix_wearables_audit_entity", f"{P}audit_entry", ["organisation_id", "entity", "entity_id"])
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(POLICY.format(table=f"{P}{table}"))


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(f"{P}{table}")
