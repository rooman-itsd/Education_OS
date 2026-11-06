"""Tables of lms (docs/data-model.md). Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module. course_offering_id, section ids, student and instructor ids, department_id, document_id and
scheduled_class_id are other modules' ids, kept by value only."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "lms_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | date | None) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return as_utc(value).isoformat()
    return value.isoformat()


def _ts(nullable: bool = False) -> Mapped:
    return mapped_column(DateTime(timezone=True), nullable=nullable)


class CourseSpace(Base, TenantMixin, TimestampMixin):
    """The learning space of one course offering (one per offering, owner decision C17)."""

    __tablename__ = f"{PREFIX}course_space"
    __table_args__ = (UniqueConstraint("organisation_id", "course_offering_id", name="uq_lms_course_space_offering"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_offering_id: Mapped[str] = mapped_column(String(36))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    visible_section_ids: Mapped[list] = mapped_column(JSON, default=list)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str] = mapped_column(String(10))
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class ContentUnit(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}content_unit"
    __table_args__ = (Index("ix_lms_content_unit_space", "organisation_id", "course_space_id", "position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    title: Mapped[str] = mapped_column(String(200))
    position: Mapped[int] = mapped_column(Integer)
    published: Mapped[bool] = mapped_column(Boolean, default=False)


class CourseMaterial(Base, TenantMixin, TimestampMixin):
    """A document (platform/documents id only; lms never stores file bytes), a link or a page."""

    __tablename__ = f"{PREFIX}course_material"
    __table_args__ = (
        Index("ix_lms_course_material_space", "organisation_id", "course_space_id", "status"),
        Index("ix_lms_course_material_published", "organisation_id", "published_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    unit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}content_unit.id"), nullable=True)
    material_type: Mapped[str] = mapped_column(String(10))
    title: Mapped[str] = mapped_column(String(200))
    document_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    body: Mapped[str | None] = mapped_column(Text, nullable=True)
    scheduled_class_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    visible_section_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(12))
    published_at: Mapped[datetime | None] = _ts(nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Assignment(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}assignment"
    __table_args__ = (Index("ix_lms_assignment_space", "organisation_id", "course_space_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    unit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}content_unit.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    instructions: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_at: Mapped[datetime] = _ts()
    max_points: Mapped[float] = mapped_column(Float)
    submission_type: Mapped[str] = mapped_column(String(14))
    max_attempts: Mapped[int] = mapped_column(Integer, default=1)
    accept_late: Mapped[bool] = mapped_column(Boolean, default=False)
    late_cutoff_at: Mapped[datetime | None] = _ts(nullable=True)
    target_section_ids: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(10))
    published_at: Mapped[datetime | None] = _ts(nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Submission(Base, TenantMixin):
    """One student's response to an assignment, per attempt. Never deleted (FR-20)."""

    __tablename__ = f"{PREFIX}submission"
    __table_args__ = (
        UniqueConstraint("organisation_id", "assignment_id", "student_id", "attempt", name="uq_lms_submission_attempt"),
        Index("ix_lms_submission_assignment_status", "organisation_id", "assignment_id", "status"),
        Index("ix_lms_submission_student", "organisation_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assignment_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}assignment.id"))
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    student_id: Mapped[str] = mapped_column(String(36))
    attempt: Mapped[int] = mapped_column(Integer)
    document_ids: Mapped[list] = mapped_column(JSON, default=list)
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime] = _ts()
    late: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(12))


class Quiz(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}quiz"
    __table_args__ = (Index("ix_lms_quiz_space", "organisation_id", "course_space_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    unit_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}content_unit.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(200))
    opens_at: Mapped[datetime] = _ts()
    closes_at: Mapped[datetime] = _ts()
    time_limit_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    attempts_allowed: Mapped[int] = mapped_column(Integer, default=1)
    attempt_scoring: Mapped[str] = mapped_column(String(10))
    auto_release: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(10))
    published_at: Mapped[datetime | None] = _ts(nullable=True)
    created_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class QuizQuestion(Base, TenantMixin):
    """Replaced as a whole while the quiz is a draft; frozen once it is published."""

    __tablename__ = f"{PREFIX}quiz_question"
    __table_args__ = (Index("ix_lms_quiz_question_quiz", "organisation_id", "quiz_id", "position"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    quiz_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}quiz.id"))
    position: Mapped[int] = mapped_column(Integer)
    question_type: Mapped[str] = mapped_column(String(16))
    prompt: Mapped[str] = mapped_column(Text)
    options: Mapped[list | None] = mapped_column(JSON, nullable=True)
    answer_key: Mapped[object | None] = mapped_column(JSON, nullable=True)
    points: Mapped[float] = mapped_column(Float)


class QuizAttempt(Base, TenantMixin):
    """One student's attempt at a quiz. question_scores holds the instructor's essay scores by question id.
    Never deleted (FR-20)."""

    __tablename__ = f"{PREFIX}quiz_attempt"
    __table_args__ = (
        UniqueConstraint("organisation_id", "quiz_id", "student_id", "attempt_number", name="uq_lms_quiz_attempt"),
        Index("ix_lms_quiz_attempt_quiz_state", "organisation_id", "quiz_id", "manual_grading_state"),
        Index("ix_lms_quiz_attempt_student", "organisation_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    quiz_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}quiz.id"))
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    student_id: Mapped[str] = mapped_column(String(36))
    attempt_number: Mapped[int] = mapped_column(Integer)
    started_at: Mapped[datetime] = _ts()
    must_submit_by: Mapped[datetime] = _ts()
    submitted_at: Mapped[datetime | None] = _ts(nullable=True)
    submitted_by_system: Mapped[bool] = mapped_column(Boolean, default=False)
    answers: Mapped[list] = mapped_column(JSON, default=list)
    question_scores: Mapped[dict] = mapped_column(JSON, default=dict)
    auto_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    manual_grading_state: Mapped[str] = mapped_column(String(10))
    status: Mapped[str] = mapped_column(String(12))


class Grade(Base, TenantMixin, TimestampMixin):
    """One coursework grade per (assignment or quiz, student). Not an examination result. `source` is `attempts` while
    a quiz grade follows its attempts and `manual` once an instructor entered it. Never deleted (FR-20)."""

    __tablename__ = f"{PREFIX}grade"
    __table_args__ = (
        UniqueConstraint("organisation_id", "item_type", "item_id", "student_id", name="uq_lms_grade_item_student"),
        Index("ix_lms_grade_space_student", "organisation_id", "course_space_id", "student_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    item_type: Mapped[str] = mapped_column(String(10))
    item_id: Mapped[str] = mapped_column(String(36))
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    student_id: Mapped[str] = mapped_column(String(36))
    points: Mapped[float] = mapped_column(Float)
    max_points: Mapped[float] = mapped_column(Float)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(10))
    version: Mapped[int] = mapped_column(Integer, default=1)
    released_at: Mapped[datetime | None] = _ts(nullable=True)
    change_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    source: Mapped[str] = mapped_column(String(10))
    graded_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class DiscussionThread(Base, TenantMixin, TimestampMixin):
    """State is derived from the two flags (open, locked or hidden), so unhiding restores what it was."""

    __tablename__ = f"{PREFIX}discussion_thread"
    __table_args__ = (Index("ix_lms_thread_space", "organisation_id", "course_space_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_space_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}course_space.id"))
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36))
    locked: Mapped[bool] = mapped_column(Boolean, default=False)
    hidden: Mapped[bool] = mapped_column(Boolean, default=False)
    last_activity_at: Mapped[datetime] = _ts()


class DiscussionPost(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}discussion_post"
    __table_args__ = (Index("ix_lms_post_thread", "organisation_id", "thread_id", "created_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    thread_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}discussion_thread.id"))
    body: Mapped[str] = mapped_column(Text)
    created_by: Mapped[str] = mapped_column(String(36))
    state: Mapped[str] = mapped_column(String(10))


# ---------------------------------------------------------------- read models (consumed events, docs/prd.md section 12)


class OfferingRef(Base, TenantMixin):
    """A course offering as academic-management publishes it. Known once its creation event arrived."""

    __tablename__ = f"{PREFIX}offering_ref"
    __table_args__ = (UniqueConstraint("organisation_id", "course_offering_id", name="uq_lms_offering_ref"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_offering_id: Mapped[str] = mapped_column(String(36))
    academic_period_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    course_code: Mapped[str | None] = mapped_column(String(40), nullable=True)
    course_title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    department_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status_as_of: Mapped[datetime | None] = _ts(nullable=True)


class InstructorRef(Base, TenantMixin):
    """An instructor assignment (academic-management faculty-assignment events). instructor_id is the identity user id
    (docs/prd.md LQ5)."""

    __tablename__ = f"{PREFIX}instructor_ref"
    __table_args__ = (
        UniqueConstraint("organisation_id", "instructor_assignment_id", name="uq_lms_instructor_ref"),
        Index("ix_lms_instructor_ref_person", "organisation_id", "instructor_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    instructor_assignment_id: Mapped[str] = mapped_column(String(36))
    course_offering_id: Mapped[str] = mapped_column(String(36))
    section_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    instructor_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(String(10))
    status_as_of: Mapped[datetime | None] = _ts(nullable=True)


class MemberRef(Base, TenantMixin):
    """A student's course registration (enrolment-registration events). student_id is the event's person_id, the
    student-information person. A learner's own reads find it from their identity user id through PersonAccount, and
    fall back to the user id itself while no link is known (docs/prd.md LQ6)."""

    __tablename__ = f"{PREFIX}member_ref"
    __table_args__ = (
        UniqueConstraint("organisation_id", "registration_id", name="uq_lms_member_ref"),
        Index("ix_lms_member_ref_person", "organisation_id", "student_id", "status"),
        Index("ix_lms_member_ref_offering", "organisation_id", "course_offering_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    registration_id: Mapped[str] = mapped_column(String(36))
    course_offering_id: Mapped[str] = mapped_column(String(36))
    section_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    student_id: Mapped[str] = mapped_column(String(36))
    student_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(10))
    status_as_of: Mapped[datetime | None] = _ts(nullable=True)


class PersonAccount(Base, TenantMixin):
    """Which student-information person a sign-in account is (student-information.person.account-linked). One row per
    person; identity_user_id is null once the link is cleared. linked_as_of is the envelope occurred_at of the event
    that set the row, so an older event never replaces a newer link."""

    __tablename__ = f"{PREFIX}person_account"
    __table_args__ = (
        UniqueConstraint("organisation_id", "person_id", name="uq_lms_person_account"),
        Index("ix_lms_person_account_user", "organisation_id", "identity_user_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    person_id: Mapped[str] = mapped_column(String(36))
    identity_user_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    linked_as_of: Mapped[datetime | None] = _ts(nullable=True)


class ProcessedEvent(Base, TenantMixin):
    """Envelope ids of consumed events already applied, so a redelivery does nothing."""

    __tablename__ = f"{PREFIX}processed_event"
    __table_args__ = (UniqueConstraint("organisation_id", "event_id", name="uq_lms_processed_event"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    event_id: Mapped[str] = mapped_column(String(36))
    name: Mapped[str] = mapped_column(String(120))
    processed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (FR-20). Holds ids and the action only, never content.
    Stands in for the audit SDK until it ships."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_lms_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (
    CourseSpace,
    ContentUnit,
    CourseMaterial,
    Assignment,
    Submission,
    Quiz,
    QuizQuestion,
    QuizAttempt,
    Grade,
    DiscussionThread,
    DiscussionPost,
    OfferingRef,
    InstructorRef,
    MemberRef,
    ProcessedEvent,
    AuditEntry,
    PersonAccount,
)
TABLES = [m.__table__ for m in MODELS]
