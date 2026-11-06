"""Initial incident-management schema: problems, incidents, timeline updates, references, root-cause analyses,
corrective actions, the per-organisation number sequence and audit entries. Every table carries organisation_id; on
Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: incident_management_0001
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "incident_management_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "incident_management_problem",
    "incident_management_incident",
    "incident_management_timeline_update",
    "incident_management_reference",
    "incident_management_rca",
    "incident_management_corrective_action",
    "incident_management_number_sequence",
    "incident_management_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


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
        "incident_management_problem",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("affected_services", sa.JSON, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("workaround", sa.Text, nullable=True),
        _ts("resolved_at", nullable=True),
        _ts("closed_at", nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "number", name="uq_incident_management_problem_number"),
    )
    op.create_table(
        "incident_management_incident",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("number", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("affected_services", sa.JSON, nullable=False),
        sa.Column("severity", sa.String(10), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("lead_id", sa.String(36), nullable=False),
        sa.Column("responder_ids", sa.JSON, nullable=False),
        sa.Column("reported_by", sa.String(36), nullable=False),
        sa.Column("problem_id", sa.String(36), sa.ForeignKey("incident_management_problem.id"), nullable=True),
        sa.Column("resolution_summary", sa.Text, nullable=True),
        _ts("started_at"),
        _ts("mitigated_at", nullable=True),
        _ts("resolved_at", nullable=True),
        _ts("closed_at", nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "number", name="uq_incident_management_incident_number"),
    )
    op.create_table(
        "incident_management_timeline_update",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incident_management_incident.id"), nullable=False),
        sa.Column("author_id", sa.String(36), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
    )
    op.create_table(
        "incident_management_reference",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("incident_id", sa.String(36), sa.ForeignKey("incident_management_incident.id"), nullable=False),
        sa.Column("ref_module", sa.String(60), nullable=False),
        sa.Column("ref_entity", sa.String(60), nullable=False),
        sa.Column("ref_id", sa.String(100), nullable=False),
        sa.Column("relation", sa.String(20), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_by", sa.String(36), nullable=False),
        sa.UniqueConstraint(
            "organisation_id",
            "incident_id",
            "ref_module",
            "ref_entity",
            "ref_id",
            name="uq_incident_management_reference_record",
        ),
    )
    op.create_table(
        "incident_management_rca",
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("problem_id", sa.String(36), sa.ForeignKey("incident_management_problem.id"), primary_key=True),
        sa.Column("summary", sa.Text, nullable=False),
        sa.Column("root_cause", sa.Text, nullable=False),
        sa.Column("contributing_factors", sa.JSON, nullable=False),
        sa.Column("attachment_document_ids", sa.JSON, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        _ts("published_at", nullable=True),
        sa.Column("published_by", sa.String(36), nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "incident_management_corrective_action",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("problem_id", sa.String(36), sa.ForeignKey("incident_management_problem.id"), nullable=False),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("owner_id", sa.String(36), nullable=False),
        sa.Column("due_date", sa.Date, nullable=False),
        sa.Column("status", sa.String(10), nullable=False),
        sa.Column("reference", sa.JSON, nullable=True),
        _ts("completed_at", nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "incident_management_number_sequence",
        sa.Column("organisation_id", sa.String(36), primary_key=True),
        sa.Column("kind", sa.String(20), primary_key=True),
        sa.Column("last_number", sa.Integer, nullable=False),
    )
    op.create_table(
        "incident_management_audit_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        _ts("occurred_at"),
    )

    for table in TABLES:
        if table != "incident_management_number_sequence":  # keyed by organisation_id already
            op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index(
        "ix_incident_management_problem_status", "incident_management_problem", ["organisation_id", "status"]
    )
    op.create_index(
        "ix_incident_management_incident_status",
        "incident_management_incident",
        ["organisation_id", "status", "severity"],
    )
    op.create_index(
        "ix_incident_management_timeline_incident",
        "incident_management_timeline_update",
        ["organisation_id", "incident_id"],
    )
    op.create_index("ix_incident_management_reference_incident_id", "incident_management_reference", ["incident_id"])
    op.create_index(
        "ix_incident_management_corrective_action_problem_id",
        "incident_management_corrective_action",
        ["problem_id"],
    )
    op.create_index(
        "ix_incident_management_action_due",
        "incident_management_corrective_action",
        ["organisation_id", "status", "due_date"],
    )
    op.create_index(
        "ix_incident_management_action_owner",
        "incident_management_corrective_action",
        ["organisation_id", "owner_id"],
    )
    op.create_index(
        "ix_incident_management_audit_entity",
        "incident_management_audit_entry",
        ["organisation_id", "entity", "entity_id"],
    )

    _enable_rls("incident_management_problem")
    _enable_rls("incident_management_incident")
    _enable_rls("incident_management_timeline_update")
    _enable_rls("incident_management_reference")
    _enable_rls("incident_management_rca")
    _enable_rls("incident_management_corrective_action")
    _enable_rls("incident_management_number_sequence")
    _enable_rls("incident_management_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
