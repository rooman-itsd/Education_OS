"""Initial enrolment-registration schema: programme enrolments with roll numbers, registration windows, course
registrations, local copies of academic-management's terms, offerings and sections, consumed-event ids and the audit
trail. Every table carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy.

Revision ID: enrolment_registration_0001
Revises:
Create Date: 2026-10-29
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "enrolment_registration_0001"
down_revision = None
branch_labels = None
depends_on = None

ACTIVE_ENROLMENT = sa.text("status = 'active'")
CONFIRMED_REGISTRATION = sa.text("status = 'confirmed'")


def _id(name: str = "id") -> sa.Column:
    return sa.Column(name, sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "enrolment_registration_programme_enrolment",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("student_name", sa.String(200), nullable=False),
        sa.Column("programme_id", sa.String(36), nullable=False),
        sa.Column("roll_number", sa.String(32), nullable=False),
        sa.Column("start_academic_period_id", sa.String(36), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("source_application_id", sa.String(36), nullable=True),
        _ts("enrolled_at"),
        sa.Column("enrolled_by", sa.String(36), nullable=False),
        _ts("ended_at", nullable=True),
        sa.Column("end_reason", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_enrolment_registration_programme_enrolment_organisation_id",
        "enrolment_registration_programme_enrolment",
        ["organisation_id"],
    )
    op.create_index(
        "uq_enrolment_registration_programme_enrolment_roll_number",
        "enrolment_registration_programme_enrolment",
        ["organisation_id", "roll_number"],
        unique=True,
    )
    op.create_index(
        "uq_enrolment_registration_programme_enrolment_active",
        "enrolment_registration_programme_enrolment",
        ["organisation_id", "person_id", "programme_id"],
        unique=True,
        sqlite_where=ACTIVE_ENROLMENT,
        postgresql_where=ACTIVE_ENROLMENT,
    )
    op.create_index(
        "ix_enrolment_registration_programme_enrolment_programme",
        "enrolment_registration_programme_enrolment",
        ["organisation_id", "programme_id", "status"],
    )

    op.create_table(
        "enrolment_registration_roll_number_counter",
        sa.Column("organisation_id", sa.String(36), primary_key=True),
        sa.Column("year", sa.Integer, primary_key=True),
        sa.Column("last_value", sa.Integer, nullable=False),
    )
    op.create_index(
        "ix_enrolment_registration_roll_number_counter_organisation_id",
        "enrolment_registration_roll_number_counter",
        ["organisation_id"],
    )

    op.create_table(
        "enrolment_registration_registration_window",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("academic_period_id", sa.String(36), nullable=False),
        _ts("opens_at"),
        _ts("closes_at"),
        sa.Column("updated_by", sa.String(36), nullable=False),
        _ts("updated_at"),
    )
    op.create_index(
        "ix_enrolment_registration_registration_window_organisation_id",
        "enrolment_registration_registration_window",
        ["organisation_id"],
    )
    op.create_index(
        "uq_enrolment_registration_registration_window_term",
        "enrolment_registration_registration_window",
        ["organisation_id", "academic_period_id"],
        unique=True,
    )

    op.create_table(
        "enrolment_registration_course_registration",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column(
            "programme_enrolment_id",
            sa.String(36),
            sa.ForeignKey("enrolment_registration_programme_enrolment.id"),
            nullable=False,
        ),
        sa.Column("person_id", sa.String(36), nullable=False),
        sa.Column("course_offering_id", sa.String(36), nullable=False),
        sa.Column("section_id", sa.String(36), nullable=False),
        sa.Column("academic_period_id", sa.String(36), nullable=False),
        sa.Column("registration_type", sa.String(20), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("references_verified", sa.Boolean, nullable=False),
        sa.Column("section_since", sa.Date, nullable=False),
        _ts("confirmed_at"),
        sa.Column("confirmed_by", sa.String(36), nullable=False),
        _ts("withdrawn_at", nullable=True),
        sa.Column("withdrawn_by", sa.String(36), nullable=True),
        sa.Column("withdrawal_reason", sa.Text, nullable=True),
    )
    op.create_index(
        "ix_enrolment_registration_course_registration_organisation_id",
        "enrolment_registration_course_registration",
        ["organisation_id"],
    )
    op.create_index(
        "uq_enrolment_registration_course_registration_confirmed",
        "enrolment_registration_course_registration",
        ["organisation_id", "person_id", "course_offering_id"],
        unique=True,
        sqlite_where=CONFIRMED_REGISTRATION,
        postgresql_where=CONFIRMED_REGISTRATION,
    )
    op.create_index(
        "ix_enrolment_registration_course_registration_enrolment",
        "enrolment_registration_course_registration",
        ["programme_enrolment_id"],
    )
    op.create_index(
        "ix_enrolment_registration_course_registration_section",
        "enrolment_registration_course_registration",
        ["organisation_id", "section_id", "status"],
    )
    op.create_index(
        "ix_enrolment_registration_course_registration_term",
        "enrolment_registration_course_registration",
        ["organisation_id", "academic_period_id", "course_offering_id", "status"],
    )

    op.create_table(
        "enrolment_registration_term_ref",
        _id("academic_period_id"),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(40), nullable=True),
        sa.Column("name", sa.String(200), nullable=True),
        sa.Column("starts_on", sa.Date, nullable=True),
        sa.Column("ends_on", sa.Date, nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False),
    )
    op.create_index(
        "ix_enrolment_registration_term_ref_organisation_id", "enrolment_registration_term_ref", ["organisation_id"]
    )

    op.create_table(
        "enrolment_registration_offering_ref",
        _id("course_offering_id"),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("academic_period_id", sa.String(36), nullable=False),
        sa.Column("course_code", sa.String(40), nullable=True),
        sa.Column("course_title", sa.String(200), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_index(
        "ix_enrolment_registration_offering_ref_organisation_id",
        "enrolment_registration_offering_ref",
        ["organisation_id"],
    )
    op.create_index(
        "ix_enrolment_registration_offering_ref_term",
        "enrolment_registration_offering_ref",
        ["organisation_id", "academic_period_id"],
    )

    op.create_table(
        "enrolment_registration_section_ref",
        _id("section_id"),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("course_offering_id", sa.String(36), nullable=False),
        sa.Column("code", sa.String(40), nullable=True),
        sa.Column("capacity", sa.Integer, nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
    )
    op.create_index(
        "ix_enrolment_registration_section_ref_organisation_id",
        "enrolment_registration_section_ref",
        ["organisation_id"],
    )
    op.create_index(
        "ix_enrolment_registration_section_ref_offering",
        "enrolment_registration_section_ref",
        ["organisation_id", "course_offering_id"],
    )

    op.create_table(
        "enrolment_registration_processed_event",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("event_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        _ts("processed_at"),
    )
    op.create_index(
        "ix_enrolment_registration_processed_event_organisation_id",
        "enrolment_registration_processed_event",
        ["organisation_id"],
    )
    op.create_index(
        "uq_enrolment_registration_processed_event_event",
        "enrolment_registration_processed_event",
        ["organisation_id", "event_id"],
        unique=True,
    )

    op.create_table(
        "enrolment_registration_audit_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=False),
        sa.Column("actor", sa.String(36), nullable=True),
        sa.Column("action", sa.String(60), nullable=False),
        sa.Column("entity", sa.String(40), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("detail", sa.JSON, nullable=True),
        _ts("occurred_at"),
    )
    op.create_index(
        "ix_enrolment_registration_audit_entry_organisation_id",
        "enrolment_registration_audit_entry",
        ["organisation_id"],
    )
    op.create_index(
        "ix_enrolment_registration_audit_entry_entity", "enrolment_registration_audit_entry", ["entity", "entity_id"]
    )

    # One literal call per table: tools/scripts/check-migrations.py looks for each table name in an rls call.
    _enable_rls("enrolment_registration_programme_enrolment")
    _enable_rls("enrolment_registration_roll_number_counter")
    _enable_rls("enrolment_registration_registration_window")
    _enable_rls("enrolment_registration_course_registration")
    _enable_rls("enrolment_registration_term_ref")
    _enable_rls("enrolment_registration_offering_ref")
    _enable_rls("enrolment_registration_section_ref")
    _enable_rls("enrolment_registration_processed_event")
    _enable_rls("enrolment_registration_audit_entry")


def downgrade() -> None:
    op.drop_table("enrolment_registration_course_registration")
    op.drop_table("enrolment_registration_programme_enrolment")
    op.drop_table("enrolment_registration_roll_number_counter")
    op.drop_table("enrolment_registration_registration_window")
    op.drop_table("enrolment_registration_term_ref")
    op.drop_table("enrolment_registration_offering_ref")
    op.drop_table("enrolment_registration_section_ref")
    op.drop_table("enrolment_registration_processed_event")
    op.drop_table("enrolment_registration_audit_entry")
