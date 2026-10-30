"""The scheduler loop's one pass (`tick`), and the run lifecycle it drives.

A due schedule becomes a `scheduler_run` row (running) and a `scheduler.job.due` event in the same transaction;
the owning module consumes the event, does the work and publishes `<module>.job.finished`, which closes the run
(`finish`). A run nobody closes within SCHEDULER_RUN_TIMEOUT_S is failed. Every outcome is also an event
(`scheduler.run.succeeded|failed|skipped`), so a job that stops running is visible without reading logs.

The tick runs in platform scope: it fires every organisation's schedules and the platform's own. On Postgres the
due rows are claimed FOR UPDATE SKIP LOCKED, so a second scheduler process cannot fire the same window."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta

from eos_core.db import SessionLocal, utcnow
from eos_core.events import publish
from eos_core.tenant import platform_scope
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..domain.cron import Cron
from ..domain.models import Run, Schedule
from ..infrastructure.config import SchedulerConfig
from .jobs import Job

log = logging.getLogger("eos.scheduler")

MAX_WINDOWS = 10_000  # counting missed windows of a per-minute job over a week stays well under this


@dataclass(frozen=True)
class TickResult:
    fired: int = 0
    skipped: int = 0
    timed_out: int = 0


def aware(value: datetime | None, like: datetime) -> datetime | None:
    """SQLite returns naive datetimes; every stored time is UTC."""
    if value is not None and value.tzinfo is None:
        return value.replace(tzinfo=like.tzinfo)
    return value


def next_window(schedule: Schedule, after: datetime) -> datetime | None:
    if schedule.cron:
        return Cron.parse(schedule.cron).next_after(after, schedule.timezone or "UTC")
    return None  # a one-off has no next window once it fired


def due_payload(run: Run, schedule: Schedule) -> dict:
    return {
        "run_id": run.id,
        "schedule_id": schedule.id,
        "job": schedule.job,
        "scope": schedule.scope,
        "trigger": run.trigger,
        "arguments": schedule.arguments or {},
        "missed_windows": run.missed_windows,
    }


def start_run(db: Session, schedule: Schedule, now: datetime, trigger: str, missed: int = 0) -> Run:
    run = Run(
        organisation_id=schedule.organisation_id,
        schedule_id=schedule.id,
        job=schedule.job,
        status="running",
        trigger=trigger,
        started_at=now,
        missed_windows=missed,
    )
    db.add(run)
    db.flush()
    publish(db, "scheduler.job.due", schedule.organisation_id, due_payload(run, schedule)).occurred_at = now
    schedule.last_run_at, schedule.last_status = now, "running"
    return run


def running_run(db: Session, schedule: Schedule) -> Run | None:
    return db.scalar(select(Run).where(Run.schedule_id == schedule.id, Run.status == "running").limit(1))


class Ticker:
    def __init__(
        self,
        jobs: dict[str, Job],
        config: SchedulerConfig,
        session_factory: Callable[[], Session] = SessionLocal,
        clock: Callable[[], datetime] = utcnow,
    ):
        self.jobs = jobs
        self.config = config
        self._sessions = session_factory
        self._now = clock

    def seed_platform_defaults(self) -> int:
        """A platform job that ships a default timing gets a schedule (in UTC) the first time it is seen, so
        billing.expire-trials runs without anyone having to create it. Removing or retiming it later sticks."""
        now, created = self._now(), 0
        with platform_scope(), self._sessions() as db:
            for job in self.jobs.values():
                if job.scope != "platform" or not job.default_cron or not job.idempotent:
                    continue
                if db.scalar(select(Schedule.id).where(Schedule.job == job.key).limit(1)):
                    continue
                schedule = Schedule(
                    organisation_id=None,
                    job=job.key,
                    scope="platform",
                    cron=job.default_cron,
                    timezone="UTC",
                    arguments={},
                    enabled=True,
                    allow_overlap=False,
                    catch_up=self.config.default_catch_up,
                    created_at=now,
                )
                schedule.next_run_at = next_window(schedule, now)
                db.add(schedule)
                created += 1
            db.commit()
        return created

    def tick(self) -> TickResult:
        now = self._now()
        with platform_scope(), self._sessions() as db:
            timed_out = self._time_out(db, now)
            fired = skipped = 0
            for schedule in self._due(db, now):
                if self._fire(db, schedule, now):
                    fired += 1
                else:
                    skipped += 1
            db.commit()
        return TickResult(fired=fired, skipped=skipped, timed_out=timed_out)

    def _due(self, db: Session, now: datetime) -> list[Schedule]:
        q = (
            select(Schedule)
            .where(Schedule.enabled.is_(True), Schedule.next_run_at.is_not(None), Schedule.next_run_at <= now)
            .order_by(Schedule.next_run_at, Schedule.id)
        )
        if db.get_bind().dialect.name == "postgresql":
            q = q.with_for_update(skip_locked=True)
        return list(db.scalars(q))

    def _fire(self, db: Session, schedule: Schedule, now: datetime) -> bool:
        window = aware(schedule.next_run_at, now)
        latest, missed = window, 0
        if schedule.cron:
            while missed < MAX_WINDOWS and (following := next_window(schedule, latest)) <= now:
                latest, missed = following, missed + 1
        schedule.next_run_at = next_window(schedule, now)

        job = self.jobs.get(schedule.job)
        if job is None or not job.idempotent:
            run = self._closed_run(
                db, schedule, now, "failed", "no installed module declares this as an idempotent job"
            )
            publish(
                db,
                "scheduler.run.failed",
                schedule.organisation_id,
                {
                    "run_id": run.id,
                    "schedule_id": schedule.id,
                    "job": schedule.job,
                    "detail": run.detail,
                },
            ).occurred_at = now
            return False
        if (now - latest).total_seconds() > self.config.catch_up_horizon_s or (missed and schedule.catch_up == "never"):
            log.warning("schedule %s (%s): %s missed window(s) not run", schedule.id, schedule.job, missed + 1)
            return False
        if not schedule.allow_overlap and running_run(db, schedule) is not None:
            self._closed_run(db, schedule, now, "skipped", "the previous run was still going")
            publish(
                db,
                "scheduler.run.skipped",
                schedule.organisation_id,
                {
                    "schedule_id": schedule.id,
                    "job": schedule.job,
                    "reason": "overlap",
                    "window_at": latest.isoformat(),
                },
            ).occurred_at = now
            return False
        start_run(db, schedule, now, "catch_up" if missed else "schedule", missed)
        return True

    @staticmethod
    def _closed_run(db: Session, schedule: Schedule, now: datetime, status: str, detail: str) -> Run:
        run = Run(
            organisation_id=schedule.organisation_id,
            schedule_id=schedule.id,
            job=schedule.job,
            status=status,
            trigger="schedule",
            started_at=now,
            finished_at=now,
            duration_ms=0,
            missed_windows=0,
            detail=detail,
        )
        db.add(run)
        db.flush()
        schedule.last_run_at, schedule.last_status = now, status
        return run

    def _time_out(self, db: Session, now: datetime) -> int:
        cutoff = now - timedelta(seconds=self.config.run_timeout_s)
        late = list(db.scalars(select(Run).where(Run.status == "running", Run.started_at < cutoff)))
        for run in late:
            detail = f"no outcome reported within {self.config.run_timeout_s} s"
            close(db, run, "failed", detail, now)
        return len(late)

    def prune(self) -> int:
        cutoff = self._now() - timedelta(days=self.config.run_retention_days)
        with platform_scope(), self._sessions() as db:
            removed = db.execute(delete(Run).where(Run.status != "running", Run.started_at < cutoff)).rowcount
            db.commit()
        return removed or 0


def close(db: Session, run: Run, status: str, detail: str | None, now: datetime) -> None:
    """End a running run once, record it on its schedule and announce the outcome."""
    run.status, run.finished_at = status, now
    run.duration_ms = max(int((now - aware(run.started_at, now)).total_seconds() * 1000), 0)
    run.detail = (detail or "")[:2000] or None
    schedule = db.get(Schedule, run.schedule_id)
    # Only the schedule's latest run speaks for it: a late report from an older run must not hide a newer one.
    if schedule is not None and (
        schedule.last_run_at is None or aware(run.started_at, now) >= aware(schedule.last_run_at, now)
    ):
        schedule.last_status = status
    payload = {"run_id": run.id, "schedule_id": run.schedule_id, "job": run.job, "detail": run.detail or ""}
    if status == "succeeded":
        payload["duration_ms"] = run.duration_ms
    publish(db, f"scheduler.run.{status}", run.organisation_id, payload).occurred_at = now
