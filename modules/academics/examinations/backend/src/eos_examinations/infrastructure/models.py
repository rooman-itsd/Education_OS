"""Tables of examinations. Every table carries organisation_id (TenantMixin), so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name (the convention every module with a backend follows);
no foreign key leaves this module. academic_period_id, course_offering_id, course_id and department_id
(academic-management) and staff_id (platform/identity) are external ids, stored as plain strings.

This is the foundation: the configuration side of the PRD's data model (cycles, grading and assessment schemes, papers,
sessions, duties, the offering read model and the audit entry). Not here, because they depend on decisions that are not
taken (docs/reviewer-decisions.md): `candidate`, `hall_ticket`, `mark_entry`, `result` (they carry `student_id`, whose
mapping is unconfirmed, and eligibility) and `registration_ref`."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id
from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "examinations_"
PERCENT = Numeric(5, 2, asdecimal=True)  # 0 to 100, two places
MARKS = Numeric(8, 2, asdecimal=True)
POINTS = Numeric(5, 2, asdecimal=True)
CREDITS = Numeric(6, 2, asdecimal=True)


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


class GradingSchemeRow(Base, TenantMixin, TimestampMixin):
    """One organisation default at most (FR-3): the partial unique index allows a single row with `is_default` per
    organisation."""

    __tablename__ = f"{PREFIX}grading_scheme"
    __table_args__ = (
        Index(
            "uq_examinations_grading_scheme_default",
            "organisation_id",
            unique=True,
            postgresql_where=text("is_default"),
            sqlite_where=text("is_default"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    name: Mapped[str] = mapped_column(String(200))
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)


class GradingBandRow(Base, TenantMixin):
    __tablename__ = f"{PREFIX}grading_band"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    grading_scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}grading_scheme.id"), index=True)
    min_percent: Mapped[Decimal] = mapped_column(PERCENT)
    max_percent: Mapped[Decimal] = mapped_column(PERCENT)
    grade: Mapped[str] = mapped_column(String(20))
    grade_point: Mapped[Decimal] = mapped_column(POINTS)
    is_pass: Mapped[bool] = mapped_column(Boolean)


class ExamCycleRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}exam_cycle"
    __table_args__ = (Index("ix_examinations_cycle_period", "organisation_id", "academic_period_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    academic_period_id: Mapped[str] = mapped_column(String(36))
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    cycle_type: Mapped[str] = mapped_column(String(20))
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    grading_scheme_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}grading_scheme.id"), index=True)
    eligibility_cutoff_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    min_attendance_percent: Mapped[Decimal | None] = mapped_column(PERCENT, nullable=True)
    check_dues: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(20))


class AssessmentSchemeRow(Base, TenantMixin, TimestampMixin):
    """Versions of a course offering's assessment scheme are kept; the partial unique index allows one `active` row per
    organisation and offering (FR-2)."""

    __tablename__ = f"{PREFIX}assessment_scheme"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "course_offering_id", "version", name="uq_examinations_assessment_scheme_version"
        ),
        Index(
            "uq_examinations_assessment_scheme_active",
            "organisation_id",
            "course_offering_id",
            unique=True,
            postgresql_where=text("status = 'active'"),
            sqlite_where=text("status = 'active'"),
        ),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_offering_id: Mapped[str] = mapped_column(String(36))
    version: Mapped[int] = mapped_column(Integer)
    pass_percent: Mapped[Decimal] = mapped_column(PERCENT)
    status: Mapped[str] = mapped_column(String(20))


class AssessmentComponentRow(Base, TenantMixin):
    __tablename__ = f"{PREFIX}assessment_component"
    __table_args__ = (
        UniqueConstraint("organisation_id", "assessment_scheme_id", "code", name="uq_examinations_component_code"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    assessment_scheme_id: Mapped[str] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}assessment_scheme.id"), index=True
    )
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20))
    weightage_percent: Mapped[Decimal] = mapped_column(PERCENT)
    max_marks: Mapped[Decimal] = mapped_column(MARKS)
    pass_marks: Mapped[Decimal | None] = mapped_column(MARKS, nullable=True)


class ExamPaperRow(Base, TenantMixin, TimestampMixin):
    """One paper per examined component and cycle (FR-4)."""

    __tablename__ = f"{PREFIX}exam_paper"
    __table_args__ = (
        UniqueConstraint(
            "organisation_id", "exam_cycle_id", "assessment_component_id", name="uq_examinations_paper_component"
        ),
        Index("ix_examinations_paper_offering", "organisation_id", "course_offering_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    exam_cycle_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}exam_cycle.id"), index=True)
    course_offering_id: Mapped[str] = mapped_column(String(36))
    assessment_component_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}assessment_component.id"))
    max_marks: Mapped[Decimal] = mapped_column(MARKS)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20))


class ExamSessionRow(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}exam_session"
    __table_args__ = (Index("ix_examinations_session_window", "organisation_id", "starts_at"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    exam_cycle_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}exam_cycle.id"), index=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ends_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    venue_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    invigilators_required: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(20))
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class ExamSessionPaperRow(Base, TenantMixin):
    """The papers written in a session. A paper is in at most one session (FR-5)."""

    __tablename__ = f"{PREFIX}session_paper"
    __table_args__ = (UniqueConstraint("organisation_id", "exam_paper_id", name="uq_examinations_session_paper"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    exam_session_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}exam_session.id"), index=True)
    exam_paper_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}exam_paper.id"))


class ExamDutyRow(Base, TenantMixin, TimestampMixin):
    """Invigilation covers a session, evaluation and moderation a paper, never both (FR-9): a check constraint holds the
    rule below the application."""

    __tablename__ = f"{PREFIX}exam_duty"
    __table_args__ = (
        CheckConstraint(
            "(duty_type = 'invigilation' AND exam_session_id IS NOT NULL AND exam_paper_id IS NULL) OR "
            "(duty_type <> 'invigilation' AND exam_paper_id IS NOT NULL AND exam_session_id IS NULL)",
            name="ck_examinations_duty_target",
        ),
        Index("ix_examinations_duty_staff", "organisation_id", "staff_id", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    exam_cycle_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}exam_cycle.id"), index=True)
    staff_id: Mapped[str] = mapped_column(String(36))
    duty_type: Mapped[str] = mapped_column(String(20))
    exam_session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}exam_session.id"), nullable=True, index=True
    )
    exam_paper_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}exam_paper.id"), nullable=True, index=True
    )
    status: Mapped[str] = mapped_column(String(20))
    cancel_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)


class OfferingRef(Base, TenantMixin, TimestampMixin):
    """Read model of an academic-management course offering (PRD section 9), for the papers of an offering and the
    reports that group by department. Not written yet: the consumer is a later slice, and `course.updated` /
    `offering.updated` carry no new values (docs/reviewer-decisions.md)."""

    __tablename__ = f"{PREFIX}offering_ref"
    __table_args__ = (UniqueConstraint("organisation_id", "course_offering_id", name="uq_examinations_offering_ref"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    course_offering_id: Mapped[str] = mapped_column(String(36))
    course_id: Mapped[str] = mapped_column(String(36))
    academic_period_id: Mapped[str] = mapped_column(String(36))
    course_code: Mapped[str] = mapped_column(String(40))
    course_title: Mapped[str] = mapped_column(String(200))
    credits: Mapped[Decimal] = mapped_column(CREDITS)
    department_id: Mapped[str] = mapped_column(String(36))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (FR-19). Interim, until the audit SDK ships: the columns follow
    platform/audit's `Record` so each row can be backfilled to `POST /records` with its `client_token`, which makes the
    backfill idempotent. `before` and `after` hold changed fields only, never a whole entity or personal details."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_examinations_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_examinations_audit_client_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_token: Mapped[str] = mapped_column(String(120))
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(String(300))
    before: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)  # SQL NULL, not JSON null
    after: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [
    m.__table__
    for m in (
        GradingSchemeRow,
        GradingBandRow,
        ExamCycleRow,
        AssessmentSchemeRow,
        AssessmentComponentRow,
        ExamPaperRow,
        ExamSessionRow,
        ExamSessionPaperRow,
        ExamDutyRow,
        OfferingRef,
        AuditEntry,
    )
]
