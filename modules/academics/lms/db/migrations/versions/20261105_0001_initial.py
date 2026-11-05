"""Initial lms schema: course spaces, content units, materials, assignments, submissions, quizzes and their questions
and attempts, coursework grades, discussion threads and posts, the read models filled by consumed events (offerings,
instructor assignments, course registrations), processed event ids and audit entries. Every table carries
organisation_id; on Postgres each gets the tenant_isolation row-level-security policy, forced.

Revision ID: lms_0001
Revises:
Create Date: 2026-11-05
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from eos_core.rls import POLICY

revision = "lms_0001"
down_revision = None
branch_labels = None
depends_on = None

TABLES = [
    "lms_course_space",
    "lms_content_unit",
    "lms_course_material",
    "lms_assignment",
    "lms_submission",
    "lms_quiz",
    "lms_quiz_question",
    "lms_quiz_attempt",
    "lms_grade",
    "lms_discussion_thread",
    "lms_discussion_post",
    "lms_offering_ref",
    "lms_instructor_ref",
    "lms_member_ref",
    "lms_processed_event",
    "lms_audit_entry",
]


def _id() -> sa.Column:
    return sa.Column("id", sa.String(36), primary_key=True)


def _ts(name: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.DateTime(timezone=True), nullable=nullable)


def _ref(name: str, table: str, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(36), sa.ForeignKey(f"{table}.id"), nullable=nullable)


def _str(name: str, length: int, nullable: bool = False) -> sa.Column:
    return sa.Column(name, sa.String(length), nullable=nullable)


def _enable_rls(table: str) -> None:
    """Row-level security on app.organisation_id (eos_core.rls.POLICY). Postgres only; SQLite has none."""
    if op.get_bind().dialect.name == "postgresql":
        op.execute(POLICY.format(table=table))


def upgrade() -> None:
    op.create_table(
        "lms_course_space",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _str("course_offering_id", 36),
        _str("title", 200),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("visible_section_ids", sa.JSON, nullable=False),
        _str("department_id", 36, nullable=True),
        _str("status", 10),
        _str("created_by", 36, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "course_offering_id", name="uq_lms_course_space_offering"),
    )
    op.create_table(
        "lms_content_unit",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _ref("course_space_id", "lms_course_space"),
        _str("title", 200),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("published", sa.Boolean, nullable=False),
    )
    op.create_table(
        "lms_course_material",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _ref("course_space_id", "lms_course_space"),
        _ref("unit_id", "lms_content_unit", nullable=True),
        _str("material_type", 10),
        _str("title", 200),
        _str("document_id", 36, nullable=True),
        _str("url", 2000, nullable=True),
        sa.Column("body", sa.Text, nullable=True),
        _str("scheduled_class_id", 36, nullable=True),
        sa.Column("visible_section_ids", sa.JSON, nullable=False),
        _str("status", 12),
        _ts("published_at", nullable=True),
        _str("created_by", 36, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "lms_assignment",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _ref("course_space_id", "lms_course_space"),
        _ref("unit_id", "lms_content_unit", nullable=True),
        _str("title", 200),
        sa.Column("instructions", sa.Text, nullable=True),
        _ts("due_at"),
        sa.Column("max_points", sa.Float, nullable=False),
        _str("submission_type", 14),
        sa.Column("max_attempts", sa.Integer, nullable=False),
        sa.Column("accept_late", sa.Boolean, nullable=False),
        _ts("late_cutoff_at", nullable=True),
        sa.Column("target_section_ids", sa.JSON, nullable=False),
        _str("status", 10),
        _ts("published_at", nullable=True),
        _str("created_by", 36, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "lms_submission",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ref("assignment_id", "lms_assignment"),
        _ref("course_space_id", "lms_course_space"),
        _str("student_id", 36),
        sa.Column("attempt", sa.Integer, nullable=False),
        sa.Column("document_ids", sa.JSON, nullable=False),
        sa.Column("text", sa.Text, nullable=True),
        _ts("submitted_at"),
        sa.Column("late", sa.Boolean, nullable=False),
        _str("status", 12),
        sa.UniqueConstraint(
            "organisation_id", "assignment_id", "student_id", "attempt", name="uq_lms_submission_attempt"
        ),
    )
    op.create_table(
        "lms_quiz",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _ref("course_space_id", "lms_course_space"),
        _ref("unit_id", "lms_content_unit", nullable=True),
        _str("title", 200),
        _ts("opens_at"),
        _ts("closes_at"),
        sa.Column("time_limit_minutes", sa.Integer, nullable=True),
        sa.Column("attempts_allowed", sa.Integer, nullable=False),
        _str("attempt_scoring", 10),
        sa.Column("auto_release", sa.Boolean, nullable=False),
        _str("status", 10),
        _ts("published_at", nullable=True),
        _str("created_by", 36, nullable=True),
        _ts("updated_at"),
    )
    op.create_table(
        "lms_quiz_question",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ref("quiz_id", "lms_quiz"),
        sa.Column("position", sa.Integer, nullable=False),
        _str("question_type", 16),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("options", sa.JSON, nullable=True),
        sa.Column("answer_key", sa.JSON, nullable=True),
        sa.Column("points", sa.Float, nullable=False),
    )
    op.create_table(
        "lms_quiz_attempt",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ref("quiz_id", "lms_quiz"),
        _ref("course_space_id", "lms_course_space"),
        _str("student_id", 36),
        sa.Column("attempt_number", sa.Integer, nullable=False),
        _ts("started_at"),
        _ts("must_submit_by"),
        _ts("submitted_at", nullable=True),
        sa.Column("submitted_by_system", sa.Boolean, nullable=False),
        sa.Column("answers", sa.JSON, nullable=False),
        sa.Column("question_scores", sa.JSON, nullable=False),
        sa.Column("auto_score", sa.Float, nullable=True),
        sa.Column("manual_score", sa.Float, nullable=True),
        _str("manual_grading_state", 10),
        _str("status", 12),
        sa.UniqueConstraint("organisation_id", "quiz_id", "student_id", "attempt_number", name="uq_lms_quiz_attempt"),
    )
    op.create_table(
        "lms_grade",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _str("item_type", 10),
        _str("item_id", 36),
        _ref("course_space_id", "lms_course_space"),
        _str("student_id", 36),
        sa.Column("points", sa.Float, nullable=False),
        sa.Column("max_points", sa.Float, nullable=False),
        sa.Column("feedback", sa.Text, nullable=True),
        _str("status", 10),
        sa.Column("version", sa.Integer, nullable=False),
        _ts("released_at", nullable=True),
        sa.Column("change_reason", sa.Text, nullable=True),
        _str("source", 10),
        _str("graded_by", 36, nullable=True),
        _ts("updated_at"),
        sa.UniqueConstraint("organisation_id", "item_type", "item_id", "student_id", name="uq_lms_grade_item_student"),
    )
    op.create_table(
        "lms_discussion_thread",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _ref("course_space_id", "lms_course_space"),
        _str("title", 200),
        sa.Column("body", sa.Text, nullable=False),
        _str("created_by", 36),
        sa.Column("locked", sa.Boolean, nullable=False),
        sa.Column("hidden", sa.Boolean, nullable=False),
        _ts("last_activity_at"),
    )
    op.create_table(
        "lms_discussion_post",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _ts("created_at"),
        _ref("thread_id", "lms_discussion_thread"),
        sa.Column("body", sa.Text, nullable=False),
        _str("created_by", 36),
        _str("state", 10),
    )
    op.create_table(
        "lms_offering_ref",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _str("course_offering_id", 36),
        _str("academic_period_id", 36, nullable=True),
        _str("course_code", 40, nullable=True),
        _str("course_title", 200, nullable=True),
        _str("department_id", 36, nullable=True),
        _str("status", 20, nullable=True),
        _ts("status_as_of", nullable=True),
        sa.UniqueConstraint("organisation_id", "course_offering_id", name="uq_lms_offering_ref"),
    )
    op.create_table(
        "lms_instructor_ref",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _str("instructor_assignment_id", 36),
        _str("course_offering_id", 36),
        _str("section_id", 36, nullable=True),
        _str("instructor_id", 36),
        _str("role", 40, nullable=True),
        _str("status", 10),
        _ts("status_as_of", nullable=True),
        sa.UniqueConstraint("organisation_id", "instructor_assignment_id", name="uq_lms_instructor_ref"),
    )
    op.create_table(
        "lms_member_ref",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _str("registration_id", 36),
        _str("course_offering_id", 36),
        _str("section_id", 36, nullable=True),
        _str("student_id", 36),
        _str("student_name", 200, nullable=True),
        _str("status", 10),
        _ts("status_as_of", nullable=True),
        sa.UniqueConstraint("organisation_id", "registration_id", name="uq_lms_member_ref"),
    )
    op.create_table(
        "lms_processed_event",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _str("event_id", 36),
        _str("name", 120),
        _ts("processed_at"),
        sa.UniqueConstraint("organisation_id", "event_id", name="uq_lms_processed_event"),
    )
    op.create_table(
        "lms_audit_entry",
        _id(),
        sa.Column("organisation_id", sa.String(36), nullable=True),
        _str("actor", 36, nullable=True),
        _str("action", 60),
        _str("entity", 40),
        _str("entity_id", 36),
        _ts("occurred_at"),
    )

    for table in TABLES:
        op.create_index(f"ix_{table}_organisation_id", table, ["organisation_id"])
    op.create_index("ix_lms_content_unit_space", "lms_content_unit", ["organisation_id", "course_space_id", "position"])
    op.create_index(
        "ix_lms_course_material_space", "lms_course_material", ["organisation_id", "course_space_id", "status"]
    )
    op.create_index("ix_lms_course_material_published", "lms_course_material", ["organisation_id", "published_at"])
    op.create_index("ix_lms_assignment_space", "lms_assignment", ["organisation_id", "course_space_id", "status"])
    op.create_index(
        "ix_lms_submission_assignment_status", "lms_submission", ["organisation_id", "assignment_id", "status"]
    )
    op.create_index("ix_lms_submission_student", "lms_submission", ["organisation_id", "student_id"])
    op.create_index("ix_lms_quiz_space", "lms_quiz", ["organisation_id", "course_space_id", "status"])
    op.create_index("ix_lms_quiz_question_quiz", "lms_quiz_question", ["organisation_id", "quiz_id", "position"])
    op.create_index(
        "ix_lms_quiz_attempt_quiz_state", "lms_quiz_attempt", ["organisation_id", "quiz_id", "manual_grading_state"]
    )
    op.create_index("ix_lms_quiz_attempt_student", "lms_quiz_attempt", ["organisation_id", "student_id"])
    op.create_index("ix_lms_grade_space_student", "lms_grade", ["organisation_id", "course_space_id", "student_id"])
    op.create_index("ix_lms_thread_space", "lms_discussion_thread", ["organisation_id", "course_space_id"])
    op.create_index("ix_lms_post_thread", "lms_discussion_post", ["organisation_id", "thread_id", "created_at"])
    op.create_index(
        "ix_lms_instructor_ref_person", "lms_instructor_ref", ["organisation_id", "instructor_id", "status"]
    )
    op.create_index("ix_lms_member_ref_person", "lms_member_ref", ["organisation_id", "student_id", "status"])
    op.create_index("ix_lms_member_ref_offering", "lms_member_ref", ["organisation_id", "course_offering_id", "status"])
    op.create_index("ix_lms_audit_entity", "lms_audit_entry", ["organisation_id", "entity", "entity_id"])

    _enable_rls("lms_course_space")
    _enable_rls("lms_content_unit")
    _enable_rls("lms_course_material")
    _enable_rls("lms_assignment")
    _enable_rls("lms_submission")
    _enable_rls("lms_quiz")
    _enable_rls("lms_quiz_question")
    _enable_rls("lms_quiz_attempt")
    _enable_rls("lms_grade")
    _enable_rls("lms_discussion_thread")
    _enable_rls("lms_discussion_post")
    _enable_rls("lms_offering_ref")
    _enable_rls("lms_instructor_ref")
    _enable_rls("lms_member_ref")
    _enable_rls("lms_processed_event")
    _enable_rls("lms_audit_entry")


def downgrade() -> None:
    for table in reversed(TABLES):
        op.drop_table(table)
