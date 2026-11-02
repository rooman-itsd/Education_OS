"""Tables of skill-progress. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module (learner and evaluator ids are plain values: people are identity's and the student and staff modules')."""

from __future__ import annotations

from datetime import UTC, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "skill_progress_"


def as_utc(value: datetime | None) -> datetime | None:
    """SQLite hands back naive datetimes; everything stored is UTC."""
    if value is None:
        return None
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def iso(value: datetime | None) -> str | None:
    return None if value is None else as_utc(value).isoformat()


class _Updated:
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Framework(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}framework"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_skill_progress_framework_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="active", index=True)


class Skill(Base, TenantMixin, TimestampMixin, _Updated):
    """A skill of one framework, optionally under a parent skill of the same framework."""

    __tablename__ = f"{PREFIX}skill"
    __table_args__ = (UniqueConstraint("organisation_id", "framework_id", "code", name="uq_skill_progress_skill_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    framework_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}framework.id"), index=True)
    parent_skill_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}skill.id"), nullable=True, index=True
    )
    code: Mapped[str] = mapped_column(String(60))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(120), nullable=True)
    level_scale: Mapped[dict] = mapped_column(JSON)


class Rubric(Base, TenantMixin, TimestampMixin, _Updated):
    """Criteria for a skill (skill_id, with its framework_id) or for every skill of a framework (framework_id only)."""

    __tablename__ = f"{PREFIX}rubric"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    skill_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}skill.id"), nullable=True, index=True)
    framework_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}framework.id"), nullable=True, index=True
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    criteria: Mapped[list] = mapped_column(JSON, default=list)


class Assessment(Base, TenantMixin, TimestampMixin, _Updated):
    """One learner evaluated on one skill against one rubric. Kept as history: never deleted, only voided.
    level_key and level_rank snapshot the scale level when recorded, so a later change to the scale does not
    rewrite the learner's progression; top_level says it was the scale's highest level then."""

    __tablename__ = f"{PREFIX}assessment"
    __table_args__ = (
        Index("ix_skill_progress_assessment_learner", "organisation_id", "learner_id", "skill_id", "assessed_at"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    learner_id: Mapped[str] = mapped_column(String(36))
    evaluator_id: Mapped[str] = mapped_column(String(36), index=True)
    skill_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}skill.id"), index=True)
    rubric_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}rubric.id"), index=True)
    assessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    criterion_scores: Mapped[list] = mapped_column(JSON, default=list)
    overall_score: Mapped[float] = mapped_column(Float)
    level_achieved: Mapped[str] = mapped_column(String(120))
    level_key: Mapped[str] = mapped_column(String(60))
    level_rank: Mapped[int] = mapped_column(Integer)
    top_level: Mapped[bool] = mapped_column(Boolean, default=False)
    feedback: Mapped[str | None] = mapped_column(Text, nullable=True)
    evidence_urls: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="submitted")
    recorded_by: Mapped[str] = mapped_column(String(36))
    verified_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    voided_by: Mapped[str | None] = mapped_column(String(36), nullable=True)
    voided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when. Interim, until the audit SDK ships: the columns follow platform/audit's `Record`,
    as athlete-performance's, hostel's and helpdesk's audit tables do, so each row can be backfilled with its
    `client_token`. `before` and `after` hold changed fields only, never feedback, notes, descriptions or evidence."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_skill_progress_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_skill_progress_audit_client_token"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    client_token: Mapped[str] = mapped_column(String(120))
    actor: Mapped[str | None] = mapped_column(String(36), nullable=True)
    action: Mapped[str] = mapped_column(String(60))
    entity_type: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(36))
    summary: Mapped[str] = mapped_column(String(300))
    before: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    after: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


TABLES = [m.__table__ for m in (Framework, Skill, Rubric, Assessment, AuditEntry)]
