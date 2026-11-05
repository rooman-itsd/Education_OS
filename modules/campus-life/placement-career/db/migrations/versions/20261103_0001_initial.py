"""Initial placement-career schema: companies, drives, job openings, applications with their history, and the audit
trail. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: placement_career_0001
Revises:
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "placement_career_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "placement_career_company",
    "placement_career_drive",
    "placement_career_opening",
    "placement_career_application",
    "placement_career_application_history",
    "placement_career_audit_entry",
]
MONEY = sa.Numeric(14, 2)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "placement_career_company",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("name_key", sa.String(200), nullable=False),
        sa.Column("industry", sa.String(120), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("contact_email", sa.String(254), nullable=True),
        sa.Column("contact_phone", sa.String(40), nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.UniqueConstraint("organisation_id", "name_key", name="uq_placement_career_company_name"),
    )
    _enable_rls("placement_career_company")

    op.create_table(
        "placement_career_drive",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("placement_career_company.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("scheduled_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=True),
        sa.Column("venue", sa.String(300), nullable=True),
        sa.Column("registration_closes_on", sa.Date, nullable=True),
        sa.Column("rounds", sa.JSON, nullable=False),
        sa.Column("eligibility", sa.JSON, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
    )
    _enable_rls("placement_career_drive")

    op.create_table(
        "placement_career_opening",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("company_id", sa.String(36), sa.ForeignKey("placement_career_company.id"), nullable=False),
        sa.Column("drive_id", sa.String(36), sa.ForeignKey("placement_career_drive.id"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("ctc_per_annum", MONEY, nullable=True),
        sa.Column("positions", sa.Integer, nullable=True),
        sa.Column("applications_close_on", sa.Date, nullable=False),
        sa.Column("eligibility", sa.JSON, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        _ts("published_at", nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
    )
    _enable_rls("placement_career_opening")

    op.create_table(
        "placement_career_application",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("opening_id", sa.String(36), sa.ForeignKey("placement_career_opening.id"), nullable=False),
        sa.Column("student_id", sa.String(36), nullable=False),
        sa.Column("student_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("declares_eligible", sa.Boolean, nullable=False),
        sa.Column("declared_programme", sa.String(200), nullable=True),
        sa.Column("declared_graduating_year", sa.Integer, nullable=True),
        sa.Column("declared_cgpa", sa.Numeric(4, 2), nullable=True),
        sa.Column("declared_active_backlogs", sa.Integer, nullable=True),
        _ts("offered_at", nullable=True),
        sa.Column("offer_ctc_per_annum", MONEY, nullable=True),
        sa.Column("offer_joining_on", sa.Date, nullable=True),
        sa.Column("offer_notes", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        _ts("applied_at"),
        _ts("updated_at"),
        sa.UniqueConstraint("opening_id", "student_id", name="uq_placement_career_application_student"),
    )
    _enable_rls("placement_career_application")

    op.create_table(
        "placement_career_application_history",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("application_id", sa.String(36), sa.ForeignKey("placement_career_application.id"), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("status", sa.String(12), nullable=False),
        sa.Column("actor_id", sa.String(36), nullable=False),
        _ts("at"),
        sa.UniqueConstraint("application_id", "sequence", name="uq_placement_career_history_sequence"),
    )
    _enable_rls("placement_career_application_history")

    op.create_table(
        "placement_career_audit_entry",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        _ts("occurred_at"),
    )
    _enable_rls("placement_career_audit_entry")

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_placement_career_drive_company_id", "placement_career_drive", ["company_id"])
    op.create_index(
        "ix_placement_career_drive_status_date", "placement_career_drive", ["organisation_id", "status", "scheduled_on"]
    )
    op.create_index("ix_placement_career_opening_company_id", "placement_career_opening", ["company_id"])
    op.create_index("ix_placement_career_opening_drive_id", "placement_career_opening", ["drive_id"])
    op.create_index(
        "ix_placement_career_opening_status_close",
        "placement_career_opening",
        ["organisation_id", "status", "applications_close_on"],
    )
    op.create_index("ix_placement_career_application_opening_id", "placement_career_application", ["opening_id"])
    op.create_index("ix_placement_career_application_student_id", "placement_career_application", ["student_id"])
    op.create_index("ix_placement_career_application_status", "placement_career_application", ["status"])
    op.create_index(
        "ix_placement_career_application_history_application_id",
        "placement_career_application_history",
        ["application_id"],
    )
    op.create_index(
        "ix_placement_career_audit_entity", "placement_career_audit_entry", ["organisation_id", "entity", "entity_id"]
    )


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
