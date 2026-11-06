"""Initial rti schema: requests, referrals, responses, transfers, appeals and audit entries. Every table carries
organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: rti_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "rti_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "rti_request",
    "rti_referral",
    "rti_response",
    "rti_transfer",
    "rti_appeal",
    "rti_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _request_id() -> sa.Column:
    return sa.Column("request_id", sa.String(36), sa.ForeignKey("rti_request.id"), nullable=False)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "rti_request",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("seq", sa.Integer, nullable=False),
        sa.Column("number", sa.String(20), nullable=False),
        sa.Column("received_via", sa.String(16), nullable=False),
        sa.Column("received_on", sa.Date, nullable=False),
        sa.Column("applicant_name", sa.String(200), nullable=False),
        sa.Column("applicant_address", sa.Text, nullable=True),
        sa.Column("applicant_email", sa.String(254), nullable=True),
        sa.Column("applicant_phone", sa.String(40), nullable=True),
        sa.Column("applicant_person_id", sa.String(36), nullable=True),
        sa.Column("subject", sa.String(200), nullable=False),
        sa.Column("information_sought", sa.Text, nullable=False),
        sa.Column("fee_status", sa.String(8), nullable=False),
        sa.Column("fee_amount", sa.Numeric(12, 2), nullable=True),
        sa.Column("fee_currency", sa.String(3), nullable=True),
        sa.Column("fee_mode", sa.String(100), nullable=True),
        sa.Column("fee_receipt_reference", sa.String(100), nullable=True),
        sa.Column("officer_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(14), nullable=False),
        sa.Column("closure", sa.String(16), nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        _ts("assigned_at", nullable=True),
        _ts("responded_at", nullable=True),
        _ts("closed_at", nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "number", name="uq_rti_request_number"),
        sa.UniqueConstraint("organisation_id", "seq", name="uq_rti_request_seq"),
    )
    op.create_table(
        "rti_referral",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        _request_id(),
        sa.Column("custodian_id", sa.String(36), nullable=False),
        sa.Column("question", sa.Text, nullable=False),
        sa.Column("due_on", sa.Date, nullable=True),
        sa.Column("status", sa.String(8), nullable=False),
        sa.Column("reply", sa.Text, nullable=True),
        _ts("replied_at", nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
    )
    op.create_table(
        "rti_response",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        _request_id(),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("grounds", sa.Text, nullable=True),
        sa.Column("dispatched_on", sa.Date, nullable=False),
        sa.Column("dispatch_mode", sa.String(16), nullable=False),
        sa.Column("responded_by", sa.String(36), nullable=False),
        sa.UniqueConstraint("organisation_id", "request_id", name="uq_rti_response_request"),
    )
    op.create_table(
        "rti_transfer",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        _request_id(),
        sa.Column("authority_name", sa.String(200), nullable=False),
        sa.Column("authority_address", sa.Text, nullable=True),
        sa.Column("transferred_on", sa.Date, nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        sa.Column("transferred_by", sa.String(36), nullable=False),
        sa.UniqueConstraint("organisation_id", "request_id", name="uq_rti_transfer_request"),
    )
    op.create_table(
        "rti_appeal",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        _request_id(),
        sa.Column("filed_on", sa.Date, nullable=False),
        sa.Column("grounds", sa.Text, nullable=False),
        sa.Column("filed_by", sa.String(36), nullable=False),
        sa.Column("outcome", sa.String(14), nullable=True),
        sa.Column("decision_note", sa.Text, nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        sa.Column("decided_on", sa.Date, nullable=True),
        sa.UniqueConstraint("organisation_id", "request_id", name="uq_rti_appeal_request"),
    )
    op.create_table(
        "rti_audit_entry",
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
    op.create_index("ix_rti_request_status", "rti_request", ["organisation_id", "status"])
    op.create_index("ix_rti_request_officer", "rti_request", ["organisation_id", "officer_id"])
    op.create_index("ix_rti_referral_request", "rti_referral", ["organisation_id", "request_id"])
    op.create_index("ix_rti_referral_custodian", "rti_referral", ["organisation_id", "custodian_id", "status"])
    op.create_index("ix_rti_audit_entity", "rti_audit_entry", ["organisation_id", "entity", "entity_id"])

    _enable_rls("rti_request")
    _enable_rls("rti_referral")
    _enable_rls("rti_response")
    _enable_rls("rti_transfer")
    _enable_rls("rti_appeal")
    _enable_rls("rti_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
