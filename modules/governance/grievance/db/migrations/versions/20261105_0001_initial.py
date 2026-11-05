"""Initial grievance schema: committees and their members, cases, proceedings, updates, decisions, appeals and audit
entries. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: grievance_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "grievance_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "grievance_committee",
    "grievance_committee_member",
    "grievance_case",
    "grievance_proceeding",
    "grievance_update",
    "grievance_decision",
    "grievance_appeal",
    "grievance_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "grievance_committee",
        _id(),
        _org(),
        _created(),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "name", name="uq_grievance_committee_name"),
    )
    op.create_table(
        "grievance_committee_member",
        _id(),
        _org(),
        sa.Column("committee_id", sa.String(36), sa.ForeignKey("grievance_committee.id"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.UniqueConstraint("organisation_id", "committee_id", "person_id", name="uq_grievance_member"),
    )
    op.create_table(
        "grievance_case",
        _id(),
        _org(),
        _created(),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("number", sa.String(24), nullable=False),
        sa.Column("track", sa.String(20), nullable=False),
        sa.Column("committee_id", sa.String(36), sa.ForeignKey("grievance_committee.id"), nullable=False),
        sa.Column("complainant_id", sa.String(36), nullable=False),
        sa.Column("respondent_person_id", sa.String(36), nullable=True),
        sa.Column("respondent_description", sa.String(500), nullable=True),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("incident_date", sa.Date, nullable=True),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("closure", sa.String(12), nullable=True),
        sa.Column("not_admitted_reason", sa.String(2000), nullable=True),
        _ts("filed_at"),
        _ts("acknowledged_at", nullable=True),
        _ts("decided_at", nullable=True),
        _ts("closed_at", nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "sequence", name="uq_grievance_case_sequence"),
    )
    op.create_table(
        "grievance_proceeding",
        _id(),
        _org(),
        _created(),
        sa.Column("grievance_id", sa.String(36), sa.ForeignKey("grievance_case.id"), nullable=False),
        sa.Column("kind", sa.String(12), nullable=False),
        sa.Column("held_on", sa.Date, nullable=False),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("recorded_by", sa.String(36), nullable=False),
    )
    op.create_table(
        "grievance_update",
        _id(),
        _org(),
        _created(),
        sa.Column("grievance_id", sa.String(36), sa.ForeignKey("grievance_case.id"), nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("from_committee", sa.Boolean, nullable=False),
        sa.Column("body", sa.Text, nullable=False),
    )
    op.create_table(
        "grievance_decision",
        _id(),
        _org(),
        sa.Column("grievance_id", sa.String(36), sa.ForeignKey("grievance_case.id"), nullable=False),
        sa.Column("outcome", sa.String(16), nullable=False),
        sa.Column("findings", sa.Text, nullable=False),
        sa.Column("actions_recommended", sa.Text, nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=False),
        _ts("decided_at"),
    )
    op.create_table(
        "grievance_appeal",
        _id(),
        _org(),
        sa.Column("grievance_id", sa.String(36), sa.ForeignKey("grievance_case.id"), nullable=False),
        sa.Column("committee_id", sa.String(36), sa.ForeignKey("grievance_committee.id"), nullable=False),
        sa.Column("reason", sa.Text, nullable=False),
        _ts("filed_at"),
        sa.Column("outcome", sa.String(10), nullable=True),
        sa.Column("outcome_note", sa.Text, nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
    )
    op.create_table(
        "grievance_audit_entry",
        _id(),
        _org(),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.String(2000), nullable=True),
        _ts("occurred_at"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_grievance_committee_member_committee_id", "grievance_committee_member", ["committee_id"])
    op.create_index("ix_grievance_member_person", "grievance_committee_member", ["organisation_id", "person_id"])
    op.create_index("ix_grievance_case_status", "grievance_case", ["status"])
    op.create_index(
        "ix_grievance_case_committee_status", "grievance_case", ["organisation_id", "committee_id", "status"]
    )
    op.create_index(
        "ix_grievance_case_complainant", "grievance_case", ["organisation_id", "complainant_id", "filed_at"]
    )
    op.create_index("ix_grievance_proceeding_grievance_id", "grievance_proceeding", ["grievance_id"])
    op.create_index("ix_grievance_update_grievance_id", "grievance_update", ["grievance_id"])
    op.create_index("uq_grievance_decision_case", "grievance_decision", ["grievance_id"], unique=True)
    op.create_index("uq_grievance_appeal_case", "grievance_appeal", ["grievance_id"], unique=True)
    op.create_index("ix_grievance_appeal_committee", "grievance_appeal", ["organisation_id", "committee_id"])
    op.create_index("ix_grievance_audit_entity", "grievance_audit_entry", ["organisation_id", "entity", "entity_id"])

    for table in TABLES:
        _enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
