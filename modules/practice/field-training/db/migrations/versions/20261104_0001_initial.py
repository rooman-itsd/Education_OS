"""Initial field-training schema: sites and their supervisors, openings and their supervisors, placements, log
entries, assessments, audit entries. Every table carries organisation_id; on Postgres each gets the forced
tenant_isolation row-level-security policy.

Revision ID: field_training_0001
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "field_training_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "field_training_site",
    "field_training_site_supervisor",
    "field_training_opening",
    "field_training_opening_supervisor",
    "field_training_placement",
    "field_training_log_entry",
    "field_training_assessment",
    "field_training_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _fk(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "field_training_site",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("kind", sa.String(100), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("contact_name", sa.String(200), nullable=True),
        sa.Column("contact_email", sa.String(254), nullable=True),
        sa.Column("active", sa.Boolean, nullable=False),
        _ts("updated_at"),
    )
    op.create_table(
        "field_training_site_supervisor",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _fk("site_id", "field_training_site"),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("organisation_id", "site_id", "person_id", name="uq_field_training_site_supervisor"),
    )
    op.create_table(
        "field_training_opening",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _fk("site_id", "field_training_site"),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("discipline", sa.String(100), nullable=True),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=False),
        sa.Column("seats", sa.Integer, nullable=False),
        sa.Column("required_minutes", sa.Integer, nullable=False),
        sa.Column("allow_applications", sa.Boolean, nullable=False),
        sa.Column("eligibility", sa.Text, nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("cancel_reason", sa.Text, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "field_training_opening_supervisor",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _fk("opening_id", "field_training_opening"),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.UniqueConstraint("organisation_id", "opening_id", "person_id", name="uq_field_training_opening_supervisor"),
    )
    op.create_table(
        "field_training_placement",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _fk("opening_id", "field_training_opening"),
        _fk("site_id", "field_training_site"),
        sa.Column("trainee_id", sa.String(36), nullable=False),
        sa.Column("trainee_name", sa.String(200), nullable=True),
        sa.Column("supervisor_id", sa.String(36), nullable=True),
        sa.Column("supervisor_name", sa.String(200), nullable=True),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=False),
        sa.Column("required_minutes", sa.Integer, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("statement", sa.Text, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("hours_overridden", sa.Boolean, nullable=False),
        sa.Column("started_on", sa.Date, nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=True),
        _ts("decided_at", nullable=True),
        _ts("completed_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "field_training_log_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _fk("placement_id", "field_training_placement"),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("minutes", sa.Integer, nullable=False),
        sa.Column("activities", sa.Text, nullable=False),
        sa.Column("reflection", sa.Text, nullable=True),
        sa.Column("status", sa.String(10), nullable=False),
        _ts("submitted_at"),
        sa.Column("verified_by", sa.String(36), nullable=True),
        _ts("verified_at", nullable=True),
        sa.Column("return_reason", sa.Text, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "field_training_assessment",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _fk("placement_id", "field_training_placement"),
        sa.Column("assessor_id", sa.String(36), nullable=False),
        sa.Column("stage", sa.String(10), nullable=False),
        sa.Column("outcome", sa.String(200), nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        _ts("recorded_at"),
    )
    op.create_table(
        "field_training_audit_entry",
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
    op.create_index("ix_field_training_site_supervisor_site_id", "field_training_site_supervisor", ["site_id"])
    op.create_index(
        "ix_field_training_site_supervisor_person", "field_training_site_supervisor", ["organisation_id", "person_id"]
    )
    op.create_index("ix_field_training_opening_site_id", "field_training_opening", ["site_id"])
    op.create_index(
        "ix_field_training_opening_status_start", "field_training_opening", ["organisation_id", "status", "starts_on"]
    )
    op.create_index(
        "ix_field_training_opening_supervisor_opening_id", "field_training_opening_supervisor", ["opening_id"]
    )
    op.create_index(
        "ix_field_training_placement_trainee", "field_training_placement", ["organisation_id", "trainee_id", "status"]
    )
    op.create_index(
        "ix_field_training_placement_supervisor",
        "field_training_placement",
        ["organisation_id", "supervisor_id", "status"],
    )
    op.create_index(
        "ix_field_training_placement_opening", "field_training_placement", ["organisation_id", "opening_id", "status"]
    )
    op.create_index(
        "ix_field_training_log_placement_date", "field_training_log_entry", ["organisation_id", "placement_id", "date"]
    )
    op.create_index(
        "ix_field_training_log_placement_status",
        "field_training_log_entry",
        ["organisation_id", "placement_id", "status"],
    )
    op.create_index(
        "ix_field_training_assessment_placement",
        "field_training_assessment",
        ["organisation_id", "placement_id", "stage"],
    )
    op.create_index(
        "ix_field_training_audit_entity", "field_training_audit_entry", ["organisation_id", "entity", "entity_id"]
    )

    _enable_rls("field_training_site")
    _enable_rls("field_training_site_supervisor")
    _enable_rls("field_training_opening")
    _enable_rls("field_training_opening_supervisor")
    _enable_rls("field_training_placement")
    _enable_rls("field_training_log_entry")
    _enable_rls("field_training_assessment")
    _enable_rls("field_training_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
