"""Tables of training-video-analysis. Every table carries organisation_id (TenantMixin), so eos_core applies the
row-level-security policy on Postgres. Table names are prefixed with the module name; no foreign key leaves this
module (coach, athlete, facility, squad and user ids are plain values). Video files are not stored here: a video row
keeps the reference (video_url) to the file platform/documents holds, and its metadata."""

from __future__ import annotations

from datetime import UTC, date, datetime

from eos_core.db import Base, TenantMixin, TimestampMixin, new_id, utcnow
from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

PREFIX = "training_video_analysis_"


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


class _Updated:
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Plan(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}plan"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    coach_id: Mapped[str] = mapped_column(String(36), index=True)
    squad_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), index=True)
    objectives: Mapped[list] = mapped_column(JSON, default=list)
    created_by: Mapped[str] = mapped_column(String(36))


class Drill(Base, TenantMixin, TimestampMixin, _Updated):
    __tablename__ = f"{PREFIX}drill"
    __table_args__ = (UniqueConstraint("organisation_id", "code", name="uq_training_video_analysis_drill_code"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    code: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(80), index=True)
    intensity: Mapped[str] = mapped_column(String(20))
    target_focus: Mapped[str | None] = mapped_column(String(300), nullable=True)
    equipment_needed: Mapped[list] = mapped_column(JSON, default=list)
    standard_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)


class TrainingSession(Base, TenantMixin, TimestampMixin, _Updated):
    """A session; its attendees are rows of SessionAttendee so an athlete's sessions are one indexed query."""

    __tablename__ = f"{PREFIX}session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    plan_id: Mapped[str | None] = mapped_column(String(36), ForeignKey(f"{PREFIX}plan.id"), nullable=True, index=True)
    coach_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    facility_id: Mapped[str | None] = mapped_column(String(36), nullable=True)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scheduled_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)
    scheduled_end: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    actual_duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(20), index=True)
    drill_ids: Mapped[list] = mapped_column(JSON, default=list)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SessionAttendee(Base, TenantMixin):
    """An athlete (athlete-performance's athlete id) expected at or attending a session."""

    __tablename__ = f"{PREFIX}session_attendee"
    __table_args__ = (UniqueConstraint("session_id", "athlete_id", name="uq_training_video_analysis_session_attendee"),)

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}session.id"))
    athlete_id: Mapped[str] = mapped_column(String(36), index=True)
    position: Mapped[int] = mapped_column(Integer)


class Video(Base, TenantMixin, TimestampMixin, _Updated):
    """A video's reference and metadata; the file itself lives in platform/documents."""

    __tablename__ = f"{PREFIX}video"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    session_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey(f"{PREFIX}session.id"), nullable=True, index=True
    )
    uploader_id: Mapped[str] = mapped_column(String(36), index=True)
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    video_url: Mapped[str] = mapped_column(String(2000))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2000), nullable=True)
    duration_seconds: Mapped[float] = mapped_column(Float)
    resolution: Mapped[str | None] = mapped_column(String(20), nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    registered_by: Mapped[str] = mapped_column(String(36))


class DrillTag(Base, TenantMixin, TimestampMixin):
    __tablename__ = f"{PREFIX}drill_tag"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}video.id"), index=True)
    drill_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}drill.id"), index=True)
    start_timestamp: Mapped[float] = mapped_column(Float)
    end_timestamp: Mapped[float] = mapped_column(Float)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagged_by: Mapped[str] = mapped_column(String(36))


class Annotation(Base, TenantMixin, TimestampMixin, _Updated):
    """A time-coded coaching note; the athletes it is about are rows of AnnotationAthlete."""

    __tablename__ = f"{PREFIX}annotation"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    video_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}video.id"), index=True)
    author_id: Mapped[str] = mapped_column(String(36))
    start_timestamp: Mapped[float] = mapped_column(Float)
    end_timestamp: Mapped[float | None] = mapped_column(Float, nullable=True)
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(20))
    drawing_markup: Mapped[dict | None] = mapped_column(JSON(none_as_null=True), nullable=True)


class AnnotationAthlete(Base, TenantMixin):
    __tablename__ = f"{PREFIX}annotation_athlete"
    __table_args__ = (
        UniqueConstraint("annotation_id", "athlete_id", name="uq_training_video_analysis_annotation_athlete"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    annotation_id: Mapped[str] = mapped_column(String(36), ForeignKey(f"{PREFIX}annotation.id"))
    athlete_id: Mapped[str] = mapped_column(String(36), index=True)
    position: Mapped[int] = mapped_column(Integer)


class AthleteLink(Base, TenantMixin):
    """Which platform/identity user is which athlete, learnt from athlete-performance.athlete.registered and
    athlete.updated. It lets an athlete see only their own sessions and videos without importing athlete-performance.
    user_id is empty once the athlete's user was removed; linked_at is the time of the event that set the link."""

    __tablename__ = f"{PREFIX}athlete_link"
    __table_args__ = (
        UniqueConstraint("organisation_id", "athlete_id", name="uq_training_video_analysis_link_athlete"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    athlete_id: Mapped[str] = mapped_column(String(36))
    user_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    event_id: Mapped[str] = mapped_column(String(36))
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class AuditEntry(Base, TenantMixin):
    """Who changed what and when. Interim, until the audit SDK ships: the columns follow platform/audit's `Record`,
    as athlete-performance's audit table does, so each row can be backfilled with its `client_token`. `before` and
    `after` hold changed fields only, never titles, notes, annotation content, markup or file links
    (service.NOT_RECORDED)."""

    __tablename__ = f"{PREFIX}audit_entry"
    __table_args__ = (
        Index("ix_training_video_analysis_audit_entity", "organisation_id", "entity_type", "entity_id"),
        UniqueConstraint("organisation_id", "client_token", name="uq_training_video_analysis_audit_client_token"),
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


TABLES = [
    m.__table__
    for m in (
        Plan,
        Drill,
        TrainingSession,
        SessionAttendee,
        Video,
        DrillTag,
        Annotation,
        AnnotationAthlete,
        AthleteLink,
        AuditEntry,
    )
]
