"""Initial selection_process schema: types, processes, stages, panels, candidates, decisions, and slots.
Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: selection_process_0001
Revises:
Create Date: 2026-10-31
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "selection_process_0001"
down_revision = None
branch_labels = None
depends_on = None


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "selection_process_type",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        _ts("created_at"),
        sa.UniqueConstraint("organisation_id", "name", name="uq_selection_process_type_org_name"),
    )

    op.create_table(
        "selection_process",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("type_id", sa.String(36), sa.ForeignKey("selection_process_type.id"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("academic_year", sa.String(50), nullable=True),
        sa.Column("context", sa.JSON, nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="draft"),
        _ts("created_at"),
        _ts("updated_at"),
    )

    op.create_table(
        "selection_process_stage",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("process_id", sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("sequence", sa.Integer, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        _ts("created_at"),
        sa.UniqueConstraint("organisation_id", "process_id", "sequence", name="uq_selection_stage_process_sequence"),
    )

    op.create_table(
        "selection_process_panel",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("process_id", sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="CASCADE"), nullable=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("member_person_ids", sa.JSON, nullable=False),
        _ts("created_at"),
    )

    op.create_table(
        "selection_process_candidate",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("process_id", sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("current_stage_id", sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default="registered"),
        sa.Column("source", sa.JSON, nullable=True),
        _ts("registered_at"),
        _ts("decided_at", nullable=True),
        sa.UniqueConstraint("organisation_id", "process_id", "person_id", name="uq_selection_candidate_process_person"),
    )

    op.create_table(
        "selection_process_decision",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("selection_process_candidate.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="CASCADE"), nullable=False),
        sa.Column("panel_id", sa.String(36), sa.ForeignKey("selection_process_panel.id", ondelete="SET NULL"), nullable=True),
        sa.Column("decided_by", sa.String(36), nullable=False),
        sa.Column("outcome", sa.String(30), nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("comments", sa.Text, nullable=True),
        _ts("decided_at"),
        sa.UniqueConstraint("organisation_id", "candidate_id", "stage_id", "decided_by", name="uq_selection_decision_panelist"),
    )

    op.create_table(
        "selection_process_slot",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("process_id", sa.String(36), sa.ForeignKey("selection_process.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stage_id", sa.String(36), sa.ForeignKey("selection_process_stage.id", ondelete="CASCADE"), nullable=True),
        sa.Column("candidate_id", sa.String(36), sa.ForeignKey("selection_process_candidate.id", ondelete="SET NULL"), nullable=True),
        sa.Column("title", sa.String(200), nullable=False),
        _ts("starts_at"),
        _ts("ends_at"),
        sa.Column("status", sa.String(30), nullable=False, server_default="scheduled"),
        sa.Column("location", sa.String(200), nullable=True),
        _ts("created_at"),
    )

    op.create_index("ix_selection_process_type_organisation_id", "selection_process_type", ["organisation_id"])
    op.create_index("ix_selection_process_organisation_id", "selection_process", ["organisation_id"])
    op.create_index("ix_selection_process_stage_organisation_id", "selection_process_stage", ["organisation_id"])
    op.create_index("ix_selection_process_panel_organisation_id", "selection_process_panel", ["organisation_id"])
    op.create_index("ix_selection_process_candidate_organisation_id", "selection_process_candidate", ["organisation_id"])
    op.create_index("ix_selection_process_decision_organisation_id", "selection_process_decision", ["organisation_id"])
    op.create_index("ix_selection_process_slot_organisation_id", "selection_process_slot", ["organisation_id"])

    op.create_index("ix_selection_process_type_id", "selection_process", ["type_id"])
    op.create_index("ix_selection_process_status", "selection_process", ["status"])
    op.create_index("ix_selection_process_stage_process", "selection_process_stage", ["process_id"])
    op.create_index("ix_selection_process_panel_process", "selection_process_panel", ["process_id"])
    op.create_index("ix_selection_process_candidate_process", "selection_process_candidate", ["process_id"])
    op.create_index("ix_selection_process_candidate_person", "selection_process_candidate", ["organisation_id", "person_id"])
    op.create_index("ix_selection_process_decision_candidate", "selection_process_decision", ["candidate_id"])
    op.create_index("ix_selection_process_slot_process", "selection_process_slot", ["process_id"])
    op.create_index("ix_selection_process_slot_candidate", "selection_process_slot", ["candidate_id"])
    op.create_index("ix_selection_process_slot_starts_at", "selection_process_slot", ["starts_at"])

    _enable_rls("selection_process_type")
    _enable_rls("selection_process")
    _enable_rls("selection_process_stage")
    _enable_rls("selection_process_panel")
    _enable_rls("selection_process_candidate")
    _enable_rls("selection_process_decision")
    _enable_rls("selection_process_slot")


def downgrade() -> None:
    op.drop_table("selection_process_slot")
    op.drop_table("selection_process_decision")
    op.drop_table("selection_process_candidate")
    op.drop_table("selection_process_panel")
    op.drop_table("selection_process_stage")
    op.drop_table("selection_process")
    op.drop_table("selection_process_type")

