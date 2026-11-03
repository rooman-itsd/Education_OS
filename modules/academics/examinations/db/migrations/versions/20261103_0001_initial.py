"""Initial examinations schema, the configuration side of the PRD's data model: grading schemes and bands, exam cycles,
assessment schemes and components, exam papers, sessions and the papers in them, duties, the course-offering read model
and the audit entry. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security
policy (eos_core.rls.POLICY).

Not here, until the decisions they wait on are taken: candidates, hall tickets, mark entries, results (they carry
`student_id`) and the registration read model.

Revision ID: ex_0001
Revises:
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "ex_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "examinations_"
PERCENT = sa.Numeric(5, 2, asdecimal=True)
MARKS = sa.Numeric(8, 2, asdecimal=True)
POINTS = sa.Numeric(5, 2, asdecimal=True)
CREDITS = sa.Numeric(6, 2, asdecimal=True)
# Creation order (parents first); downgrade drops in reverse.
TABLES = [
    f"{P}grading_scheme",
    f"{P}grading_band",
    f"{P}exam_cycle",
    f"{P}assessment_scheme",
    f"{P}assessment_component",
    f"{P}exam_paper",
    f"{P}exam_session",
    f"{P}session_paper",
    f"{P}exam_duty",
    f"{P}offering_ref",
    f"{P}audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _org() -> sa.Column:
    return sa.Column("organisation_id", sa.String(36), nullable=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def _string(name: str, length: int = 36, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(length), nullable=nullable)


def _fk(name: str, target: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{P}{target}.id"), nullable=nullable)


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        f"{P}grading_scheme",
        _id(),
        _org(),
        _created(),
        _string("name", 200),
        sa.Column("is_default", sa.Boolean, nullable=False),
    )
    op.create_table(
        f"{P}grading_band",
        _id(),
        _org(),
        _fk("grading_scheme_id", "grading_scheme"),
        sa.Column("min_percent", PERCENT, nullable=False),
        sa.Column("max_percent", PERCENT, nullable=False),
        _string("grade", 20),
        sa.Column("grade_point", POINTS, nullable=False),
        sa.Column("is_pass", sa.Boolean, nullable=False),
    )
    op.create_table(
        f"{P}exam_cycle",
        _id(),
        _org(),
        _created(),
        _string("academic_period_id"),
        _string("code", 40),
        _string("name", 200),
        _string("cycle_type", 20),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=False),
        _fk("grading_scheme_id", "grading_scheme"),
        sa.Column("eligibility_cutoff_date", sa.Date, nullable=True),
        sa.Column("min_attendance_percent", PERCENT, nullable=True),
        sa.Column("check_dues", sa.Boolean, nullable=False),
        _string("status", 20),
    )
    op.create_table(
        f"{P}assessment_scheme",
        _id(),
        _org(),
        _created(),
        _string("course_offering_id"),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("pass_percent", PERCENT, nullable=False),
        _string("status", 20),
        sa.UniqueConstraint(
            "organisation_id", "course_offering_id", "version", name="uq_examinations_assessment_scheme_version"
        ),
    )
    op.create_table(
        f"{P}assessment_component",
        _id(),
        _org(),
        _fk("assessment_scheme_id", "assessment_scheme"),
        _string("code", 40),
        _string("name", 200),
        _string("kind", 20),
        sa.Column("weightage_percent", PERCENT, nullable=False),
        sa.Column("max_marks", MARKS, nullable=False),
        sa.Column("pass_marks", MARKS, nullable=True),
        sa.UniqueConstraint("organisation_id", "assessment_scheme_id", "code", name="uq_examinations_component_code"),
    )
    op.create_table(
        f"{P}exam_paper",
        _id(),
        _org(),
        _created(),
        _fk("exam_cycle_id", "exam_cycle"),
        _string("course_offering_id"),
        _fk("assessment_component_id", "assessment_component"),
        sa.Column("max_marks", MARKS, nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        _string("status", 20),
        sa.UniqueConstraint(
            "organisation_id", "exam_cycle_id", "assessment_component_id", name="uq_examinations_paper_component"
        ),
    )
    op.create_table(
        f"{P}exam_session",
        _id(),
        _org(),
        _created(),
        _fk("exam_cycle_id", "exam_cycle"),
        sa.Column("starts_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("ends_at", sa.DateTime(timezone=True), nullable=False),
        _string("venue_label", 200, nullable=True),
        sa.Column("invigilators_required", sa.Integer, nullable=False),
        _string("status", 20),
        _string("cancel_reason", 500, nullable=True),
    )
    op.create_table(
        f"{P}session_paper",
        _id(),
        _org(),
        _fk("exam_session_id", "exam_session"),
        _fk("exam_paper_id", "exam_paper"),
        sa.UniqueConstraint("organisation_id", "exam_paper_id", name="uq_examinations_session_paper"),
    )
    op.create_table(
        f"{P}exam_duty",
        _id(),
        _org(),
        _created(),
        _fk("exam_cycle_id", "exam_cycle"),
        _string("staff_id"),
        _string("duty_type", 20),
        _fk("exam_session_id", "exam_session", nullable=True),
        _fk("exam_paper_id", "exam_paper", nullable=True),
        _string("status", 20),
        _string("cancel_reason", 500, nullable=True),
        sa.CheckConstraint(
            "(duty_type = 'invigilation' AND exam_session_id IS NOT NULL AND exam_paper_id IS NULL) OR "
            "(duty_type <> 'invigilation' AND exam_paper_id IS NOT NULL AND exam_session_id IS NULL)",
            name="ck_examinations_duty_target",
        ),
    )
    op.create_table(
        f"{P}offering_ref",
        _id(),
        _org(),
        _created(),
        _string("course_offering_id"),
        _string("course_id"),
        _string("academic_period_id"),
        _string("course_code", 40),
        _string("course_title", 200),
        sa.Column("credits", CREDITS, nullable=False),
        _string("department_id"),
        sa.UniqueConstraint("organisation_id", "course_offering_id", name="uq_examinations_offering_ref"),
    )
    op.create_table(
        f"{P}audit_entry",
        _id(),
        _org(),
        _string("client_token", 120),
        _string("actor", nullable=True),
        _string("action", 60),
        _string("entity_type", 40),
        _string("entity_id"),
        _string("summary", 300),
        sa.Column("before", sa.JSON, nullable=True),
        sa.Column("after", sa.JSON, nullable=True),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_examinations_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index(f"ix_{P}grading_band_grading_scheme_id", f"{P}grading_band", ["grading_scheme_id"])
    op.create_index(f"ix_{P}exam_cycle_grading_scheme_id", f"{P}exam_cycle", ["grading_scheme_id"])
    op.create_index(
        f"ix_{P}assessment_component_assessment_scheme_id", f"{P}assessment_component", ["assessment_scheme_id"]
    )
    op.create_index(f"ix_{P}exam_paper_exam_cycle_id", f"{P}exam_paper", ["exam_cycle_id"])
    op.create_index(f"ix_{P}exam_session_exam_cycle_id", f"{P}exam_session", ["exam_cycle_id"])
    op.create_index(f"ix_{P}session_paper_exam_session_id", f"{P}session_paper", ["exam_session_id"])
    op.create_index(f"ix_{P}exam_duty_exam_cycle_id", f"{P}exam_duty", ["exam_cycle_id"])
    op.create_index(f"ix_{P}exam_duty_exam_session_id", f"{P}exam_duty", ["exam_session_id"])
    op.create_index(f"ix_{P}exam_duty_exam_paper_id", f"{P}exam_duty", ["exam_paper_id"])
    op.create_index(
        "ix_examinations_cycle_period", f"{P}exam_cycle", ["organisation_id", "academic_period_id", "status"]
    )
    op.create_index("ix_examinations_paper_offering", f"{P}exam_paper", ["organisation_id", "course_offering_id"])
    op.create_index("ix_examinations_session_window", f"{P}exam_session", ["organisation_id", "starts_at"])
    op.create_index("ix_examinations_duty_staff", f"{P}exam_duty", ["organisation_id", "staff_id", "status"])
    op.create_index("ix_examinations_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"])
    # One organisation default grading scheme, and one active assessment scheme per course offering (FR-3, FR-2).
    op.create_index(
        "uq_examinations_grading_scheme_default",
        f"{P}grading_scheme",
        ["organisation_id"],
        unique=True,
        postgresql_where=sa.text("is_default"),
        sqlite_where=sa.text("is_default"),
    )
    op.create_index(
        "uq_examinations_assessment_scheme_active",
        f"{P}assessment_scheme",
        ["organisation_id", "course_offering_id"],
        unique=True,
        postgresql_where=sa.text("status = 'active'"),
        sqlite_where=sa.text("status = 'active'"),
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
