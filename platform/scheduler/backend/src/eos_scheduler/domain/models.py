"""Schedules and their runs. organisation_id is null for a platform schedule (one run per deployment, across
every organisation, such as billing.expire-trials); such rows are read and written only in platform scope."""

from __future__ import annotations

from datetime import datetime

from eos_core.db import Base, new_id, utcnow
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

TABLE_NAMES = ("scheduler_schedule", "scheduler_run", "scheduler_seeded_default")


class Schedule(Base):
    __tablename__ = "scheduler_schedule"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    job: Mapped[str] = mapped_column(String(120), index=True)
    scope: Mapped[str] = mapped_column(String(20))  # platform | organisation
    cron: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timezone: Mapped[str | None] = mapped_column(String(64), nullable=True)
    run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    arguments: Mapped[dict] = mapped_column(JSON, default=dict)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_overlap: Mapped[bool] = mapped_column(Boolean, default=False)
    catch_up: Mapped[str] = mapped_column(String(10), default="once")  # once | never
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    next_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True, nullable=True)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_status: Mapped[str | None] = mapped_column(String(20), nullable=True)


class Run(Base):
    __tablename__ = "scheduler_run"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=new_id)
    organisation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    schedule_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("scheduler_schedule.id", ondelete="CASCADE"), index=True
    )
    job: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), index=True)  # running | succeeded | failed | skipped
    trigger: Mapped[str] = mapped_column(String(20))  # schedule | manual | catch_up
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    missed_windows: Mapped[int] = mapped_column(Integer, default=0)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)


class SeededDefault(Base):
    """A platform job whose default schedule has been created once. The primary key is the job, so two
    schedulers starting together cannot both seed it (the second insert waits, then conflicts), and the row
    outlives the schedule: an operator who deletes a seeded schedule does not see it come back on restart.
    organisation_id is always null (platform), carried with row-level security like every module table."""

    __tablename__ = "scheduler_seeded_default"
    job: Mapped[str] = mapped_column(String(120), primary_key=True)
    organisation_id: Mapped[str | None] = mapped_column(String(36), index=True, nullable=True)
    seeded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
