"""Tables of projects. Every table carries organisation_id (TenantMixin), so eos_core applies the row-level-security
policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this module.
person_id, reviewer and submitter ids refer to identity / student-information / hr-payroll by id only, and
document ids to platform/documents."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "projects_"


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


class Project(Base, TenantMixin, TimestampMixin):
    """A project: proposed by a learner or created active by a coordinator. Never deleted (PRD rule)."""

    __tablename__ = f"{PREFIX}project"
    __table_args__ = (Index("ix_projects_project_status", "organisation_id", "status"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    kind: Mapped[str | None] = mapped_column(String(100), nullable=True)
    academic_year: Mapped[str | None] = mapped_column(String(20), nullable=True)
    starts_on: Mapped[date] = mapped_column(Date)
    ends_on: Mapped[date] = mapped_column(Date)
    external_partner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    status: Mapped[str] = mapped_column(String(12))
    outcome: Mapped[str | None] = mapped_column(String(100), nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[str] = mapped_column(String(36))
    decided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Member(Base, TenantMixin):
    """A person on a project team. Leaving sets left_at; the row is kept. A person who rejoins gets a new row."""

    __tablename__ = f"{PREFIX}member"
    __table_args__ = (
        Index("ix_projects_member_person", "organisation_id", "person_id"),
        Index("ix_projects_member_project", "organisation_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}project.id"))
    person_id: Mapped[str] = mapped_column(String(36))
    role: Mapped[str] = mapped_column(String(10))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Guide(Base, TenantMixin):
    """A guide of a project. Replacing the guides sets removed_at on those no longer named; the row is kept."""

    __tablename__ = f"{PREFIX}guide"
    __table_args__ = (
        Index("ix_projects_guide_person", "organisation_id", "person_id"),
        Index("ix_projects_guide_project", "organisation_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}project.id"))
    person_id: Mapped[str] = mapped_column(String(36))
    assigned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    removed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class Milestone(Base, TenantMixin, TimestampMixin):
    """A milestone of a project. Cancelled, never deleted. overdue_flagged_at is set when the daily job has
    published projects.milestone.overdue for it, so the event goes out once per milestone."""

    __tablename__ = f"{PREFIX}milestone"
    __table_args__ = (Index("ix_projects_milestone_project", "organisation_id", "project_id", "due_on"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}project.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    due_on: Mapped[date] = mapped_column(Date)
    weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(10), index=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    overdue_flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Submission(Base, TenantMixin):
    """One submitted version of a milestone, or of the whole project (milestone_id null: the final submission).
    Every version is kept. document_ids are references to files in platform/documents."""

    __tablename__ = f"{PREFIX}submission"
    __table_args__ = (
        UniqueConstraint("organisation_id", "project_id", "milestone_id", "version", name="uq_projects_submission"),
        Index("ix_projects_submission_project", "organisation_id", "project_id"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    project_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}project.id"))
    milestone_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}milestone.id"), nullable=True)
    version: Mapped[int] = mapped_column(Integer)
    note: Mapped[str] = mapped_column(Text)
    document_ids: Mapped[list] = mapped_column(JSON, default=list)
    submitted_by: Mapped[str] = mapped_column(String(36))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class Review(Base, TenantMixin):
    """A guide's review of one submission: accepted or returned. The evaluation of a final submission is a review
    too (completed is recorded as accepted); its outcome is kept on the project."""

    __tablename__ = f"{PREFIX}review"
    __table_args__ = (UniqueConstraint("organisation_id", "submission_id", name="uq_projects_review_submission"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    submission_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}submission.id"))
    reviewer_id: Mapped[str] = mapped_column(String(36))
    decision: Mapped[str] = mapped_column(String(10))
    comments: Mapped[str | None] = mapped_column(Text, nullable=True)
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


class AuditEntry(Base, TenantMixin):
    """Who changed what and when, for every state change (PRD rule "every state change writes an audit record").
    Holds ids and the action only, never notes, comments or personal details. Stands in for the audit SDK."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (Index("ix_projects_audit_entity", "organisation_id", "entity", "entity_id"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


MODELS = (Project, Member, Guide, Milestone, Submission, Review, AuditEntry)
TABLES = [m.__table__ for m in MODELS]
