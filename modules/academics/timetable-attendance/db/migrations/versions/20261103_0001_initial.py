"""Initial timetable-attendance schema: timetables and slots, scheduled classes, attendance sessions, records and
their change history, the read models of academic-management and enrolment facts, and the audit entry. Every table
carries organisation_id; on Postgres each gets the tenant_isolation row-level-security policy (eos_core.rls.POLICY).

Revision ID: tt_0001
Revises:
Create Date: 2026-11-03
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "tt_0001"
down_revision = None
branch_labels = None
depends_on = None

P = "timetable_attendance_"
# Creation order (parents first); downgrade drops in reverse.
TABLES = [
    f"{P}timetable",
    f"{P}timetable_slot",
    f"{P}scheduled_class",
    f"{P}attendance_session",
    f"{P}attendance_record",
    f"{P}record_change",
    f"{P}offering_ref",
    f"{P}section_ref",
    f"{P}assignment_ref",
    f"{P}section_member",
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


def _instant(name: str, *, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def enable_rls(table: str) -> None:
    """Tenant isolation on Postgres: the app sets app.organisation_id per request (eos_core.rls.POLICY)."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        f"{P}timetable",
        _id(),
        _org(),
        _created(),
        _string("academic_period_id"),
        _string("department_id", nullable=True),
        _string("name", 200),
        sa.Column("version", sa.Integer, nullable=False),
        _string("status", 20),
        _instant("published_at", nullable=True),
    )
    op.create_table(
        f"{P}timetable_slot",
        _id(),
        _org(),
        sa.Column("timetable_id", sa.String(36), sa.ForeignKey(f"{P}timetable.id"), nullable=False),
        _string("day_of_week", 10),
        sa.Column("start_time", sa.Time, nullable=False),
        sa.Column("end_time", sa.Time, nullable=False),
        _string("course_offering_id"),
        _string("section_id"),
        _string("instructor_assignment_id"),
        _string("location_label", 200, nullable=True),
        sa.Column("effective_from", sa.Date, nullable=True),
        sa.Column("effective_to", sa.Date, nullable=True),
    )
    op.create_table(
        f"{P}scheduled_class",
        _id(),
        _org(),
        _created(),
        sa.Column("timetable_id", sa.String(36), sa.ForeignKey(f"{P}timetable.id"), nullable=True),
        _string("slot_id", nullable=True),
        _string("academic_period_id"),
        _string("course_offering_id"),
        _string("section_id"),
        _string("instructor_assignment_id"),
        _string("instructor_id"),
        sa.Column("class_date", sa.Date, nullable=False),
        _instant("starts_at"),
        _instant("ends_at"),
        _string("location_label", 200, nullable=True),
        _string("status", 20),
        _string("cancel_reason", 500, nullable=True),
        sa.UniqueConstraint("organisation_id", "slot_id", "class_date", name="uq_timetable_attendance_class_slot_date"),
    )
    op.create_table(
        f"{P}attendance_session",
        _id(),
        _org(),
        _created(),
        sa.Column("scheduled_class_id", sa.String(36), sa.ForeignKey(f"{P}scheduled_class.id"), nullable=False),
        _string("status", 10),
        _instant("opened_at"),
        _string("opened_by"),
        _instant("marking_deadline"),
        _instant("closed_at", nullable=True),
        _string("closed_by", nullable=True),
        sa.UniqueConstraint("organisation_id", "scheduled_class_id", name="uq_timetable_attendance_session_class"),
    )
    op.create_table(
        f"{P}attendance_record",
        _id(),
        _org(),
        _created(),
        sa.Column("attendance_session_id", sa.String(36), sa.ForeignKey(f"{P}attendance_session.id"), nullable=False),
        _string("student_id"),
        _string("status", 10, nullable=True),
        _string("remark", 500, nullable=True),
        _string("marked_by", nullable=True),
        _instant("marked_at", nullable=True),
        sa.UniqueConstraint(
            "organisation_id", "attendance_session_id", "student_id", name="uq_timetable_attendance_record_student"
        ),
    )
    op.create_table(
        f"{P}record_change",
        _id(),
        _org(),
        sa.Column("attendance_record_id", sa.String(36), sa.ForeignKey(f"{P}attendance_record.id"), nullable=False),
        _string("from_status", 10),
        _string("to_status", 10),
        sa.Column("reason", sa.Text, nullable=False),
        _string("changed_by"),
        _instant("changed_at"),
    )
    op.create_table(
        f"{P}offering_ref",
        _id(),
        _org(),
        _created(),
        _string("course_offering_id"),
        _string("academic_period_id"),
        _string("course_code", 40),
        _string("course_title", 200),
        _string("department_id", nullable=True),
        _string("status", 20),
        sa.UniqueConstraint("organisation_id", "course_offering_id", name="uq_timetable_attendance_offering_ref"),
    )
    op.create_table(
        f"{P}section_ref",
        _id(),
        _org(),
        _created(),
        _string("section_id"),
        _string("course_offering_id"),
        _string("code", 40),
        _string("status", 20),
        sa.UniqueConstraint("organisation_id", "section_id", name="uq_timetable_attendance_section_ref"),
    )
    op.create_table(
        f"{P}assignment_ref",
        _id(),
        _org(),
        _created(),
        _string("instructor_assignment_id"),
        _string("course_offering_id"),
        _string("section_id", nullable=True),
        _string("instructor_id"),
        _string("status", 20),
        sa.UniqueConstraint(
            "organisation_id", "instructor_assignment_id", name="uq_timetable_attendance_assignment_ref"
        ),
    )
    op.create_table(
        f"{P}section_member",
        _id(),
        _org(),
        _created(),
        _string("section_id"),
        _string("student_id"),
        _string("student_name", 200, nullable=True),
        sa.Column("allocated_from", sa.Date, nullable=False),
        sa.Column("allocated_to", sa.Date, nullable=True),
        sa.UniqueConstraint(
            "organisation_id", "section_id", "student_id", "allocated_from", name="uq_timetable_attendance_member"
        ),
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
        _instant("occurred_at"),
        sa.UniqueConstraint("organisation_id", "client_token", name="uq_timetable_attendance_audit_client_token"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index(f"ix_{P}timetable_slot_timetable_id", f"{P}timetable_slot", ["timetable_id"])
    op.create_index(f"ix_{P}scheduled_class_timetable_id", f"{P}scheduled_class", ["timetable_id"])
    op.create_index(
        f"ix_{P}attendance_record_attendance_session_id", f"{P}attendance_record", ["attendance_session_id"]
    )
    op.create_index(f"ix_{P}record_change_attendance_record_id", f"{P}record_change", ["attendance_record_id"])
    op.create_index(f"ix_{P}section_member_section_id", f"{P}section_member", ["section_id"])
    op.create_index(
        "ix_timetable_attendance_timetable_period", f"{P}timetable", ["organisation_id", "academic_period_id", "status"]
    )
    op.create_index("ix_timetable_attendance_slot_section", f"{P}timetable_slot", ["organisation_id", "section_id"])
    op.create_index(
        "ix_timetable_attendance_slot_assignment", f"{P}timetable_slot", ["organisation_id", "instructor_assignment_id"]
    )
    op.create_index("ix_timetable_attendance_class_date", f"{P}scheduled_class", ["organisation_id", "class_date"])
    op.create_index(
        "ix_timetable_attendance_class_instructor",
        f"{P}scheduled_class",
        ["organisation_id", "instructor_id", "class_date"],
    )
    op.create_index(
        "ix_timetable_attendance_class_section", f"{P}scheduled_class", ["organisation_id", "section_id", "class_date"]
    )
    op.create_index(
        "ix_timetable_attendance_class_offering", f"{P}scheduled_class", ["organisation_id", "course_offering_id"]
    )
    op.create_index(
        "ix_timetable_attendance_session_status",
        f"{P}attendance_session",
        ["organisation_id", "status", "marking_deadline"],
    )
    op.create_index(
        "ix_timetable_attendance_record_student", f"{P}attendance_record", ["organisation_id", "student_id"]
    )
    op.create_index("ix_timetable_attendance_member_student", f"{P}section_member", ["organisation_id", "student_id"])
    op.create_index(
        "ix_timetable_attendance_audit_entity", f"{P}audit_entry", ["organisation_id", "entity_type", "entity_id"]
    )

    for table in TABLES:
        enable_rls(table)


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
