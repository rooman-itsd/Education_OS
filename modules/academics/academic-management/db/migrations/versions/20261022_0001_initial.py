"""Initial academic-management schema: terms, programmes, courses, curricula and their items, offerings, sections,
faculty assignments, the roster read model and consumed-event ids. Every table carries organisation_id; on
Postgres each gets the tenant_isolation row-level-security policy (eos_core.rls.POLICY).

Revision ID: am_0001
Revises:
Create Date: 2026-10-22
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "am_0001"
down_revision = None
branch_labels = None
depends_on = None

AMOUNT = sa.Numeric(10, 2, asdecimal=True)
# Creation order (parents first); downgrade drops in reverse.
TABLES = [
    "academic_management_term",
    "academic_management_programme",
    "academic_management_course",
    "academic_management_curriculum",
    "academic_management_curriculum_item",
    "academic_management_offering",
    "academic_management_section",
    "academic_management_faculty_assignment",
    "academic_management_roster_entry",
    "academic_management_processed_event",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), nullable=False)


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "academic_management_term",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("starts_on", sa.Date, nullable=False),
        sa.Column("ends_on", sa.Date, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_academic_management_term_code"),
    )
    op.create_table(
        "academic_management_programme",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("department_id", sa.String(36), nullable=False),
        sa.Column("duration_terms", sa.Integer, nullable=False),
        sa.Column("credits_required", AMOUNT, nullable=False),
        sa.Column("published_curriculum_id", sa.String(36), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_academic_management_programme_code"),
    )
    op.create_table(
        "academic_management_course",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("credits", AMOUNT, nullable=False),
        sa.Column("lecture_hours", AMOUNT, nullable=True),
        sa.Column("practical_hours", AMOUNT, nullable=True),
        sa.Column("course_type", sa.String(20), nullable=False),
        sa.Column("department_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint("organisation_id", "code", name="uq_academic_management_course_code"),
    )
    op.create_table(
        "academic_management_curriculum",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("programme_id", sa.String(36), sa.ForeignKey("academic_management_programme.id"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint(
            "organisation_id", "programme_id", "version", name="uq_academic_management_curriculum_version"
        ),
    )
    op.create_index(
        "ix_academic_management_curriculum_programme_id", "academic_management_curriculum", ["programme_id"]
    )
    op.create_table(
        "academic_management_curriculum_item",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("curriculum_id", sa.String(36), sa.ForeignKey("academic_management_curriculum.id"), nullable=False),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("academic_management_course.id"), nullable=False),
        sa.Column("programme_term", sa.Integer, nullable=False),
        sa.Column("category", sa.String(20), nullable=False),
        sa.Column("credits", AMOUNT, nullable=False),
    )
    op.create_index(
        "ix_academic_management_curriculum_item_curriculum_id", "academic_management_curriculum_item", ["curriculum_id"]
    )
    op.create_table(
        "academic_management_offering",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column("course_id", sa.String(36), sa.ForeignKey("academic_management_course.id"), nullable=False),
        sa.Column("academic_period_id", sa.String(36), sa.ForeignKey("academic_management_term.id"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("programme_ids", sa.JSON, nullable=False),
    )
    op.create_index("ix_academic_management_offering_course_id", "academic_management_offering", ["course_id"])
    op.create_index(
        "ix_academic_management_offering_period",
        "academic_management_offering",
        ["organisation_id", "academic_period_id"],
    )
    op.create_table(
        "academic_management_section",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column(
            "course_offering_id", sa.String(36), sa.ForeignKey("academic_management_offering.id"), nullable=False
        ),
        sa.Column("code", sa.String(40), nullable=False),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.UniqueConstraint(
            "organisation_id", "course_offering_id", "code", name="uq_academic_management_section_code"
        ),
    )
    op.create_index(
        "ix_academic_management_section_course_offering_id", "academic_management_section", ["course_offering_id"]
    )
    op.create_table(
        "academic_management_faculty_assignment",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _created(),
        sa.Column(
            "course_offering_id", sa.String(36), sa.ForeignKey("academic_management_offering.id"), nullable=False
        ),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("academic_management_section.id"), nullable=True),
        sa.Column("faculty_id", sa.String(36), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("contact_hours", AMOUNT, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index(
        "ix_academic_management_faculty_assignment_course_offering_id",
        "academic_management_faculty_assignment",
        ["course_offering_id"],
    )
    op.create_index(
        "ix_academic_management_faculty_assignment_faculty_id", "academic_management_faculty_assignment", ["faculty_id"]
    )
    op.create_table(
        "academic_management_roster_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("registration_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column(
            "course_offering_id", sa.String(36), sa.ForeignKey("academic_management_offering.id"), nullable=False
        ),
        sa.Column("section_id", sa.String(36), sa.ForeignKey("academic_management_section.id"), nullable=False),
        sa.Column("student_name", sa.String(200), nullable=True),
        sa.Column("roll_number", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("enrolled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("withdrawn_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("organisation_id", "registration_id", name="uq_academic_management_roster_registration"),
    )
    op.create_index(
        "ix_academic_management_roster_entry_course_offering_id",
        "academic_management_roster_entry",
        ["course_offering_id"],
    )
    op.create_index(
        "ix_academic_management_roster_entry_section_id", "academic_management_roster_entry", ["section_id"]
    )
    op.create_table(
        "academic_management_processed_event",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("organisation_id", "event_id", name="uq_academic_management_processed_event"),
    )
    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    enable_rls("academic_management_term")
    enable_rls("academic_management_programme")
    enable_rls("academic_management_course")
    enable_rls("academic_management_curriculum")
    enable_rls("academic_management_curriculum_item")
    enable_rls("academic_management_offering")
    enable_rls("academic_management_section")
    enable_rls("academic_management_faculty_assignment")
    enable_rls("academic_management_roster_entry")
    enable_rls("academic_management_processed_event")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
