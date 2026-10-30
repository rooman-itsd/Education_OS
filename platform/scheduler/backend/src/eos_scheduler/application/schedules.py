"""Schedules and runs behind contracts/openapi.yaml. An organisation caller works only on its own
organisation-scoped schedules; only the super admin, in platform scope, sees every organisation's and creates or
runs platform jobs such as billing.expire-trials."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from eos_core.db import utcnow
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from ..domain.cron import Cron, CronError, zone
from ..domain.models import Run, Schedule
from ..infrastructure.config import SchedulerConfig
from .jobs import Job
from .ticker import aware, next_window, running_run, start_run

audit = logging.getLogger("eos.scheduler.audit")


class SchedulerError(Exception):
    def __init__(self, status: int, detail: str):
        super().__init__(detail)
        self.status, self.detail = status, detail


@dataclass(frozen=True)
class Scope:
    organisation_id: str | None
    platform: bool = False  # the super admin: every organisation, and platform jobs


def _scoped(q, model, scope: Scope, organisation_id: str | None = None):
    if scope.platform:
        return q if organisation_id is None else q.where(model.organisation_id == organisation_id)
    return q.where(model.organisation_id == scope.organisation_id)


def _job(jobs: dict[str, Job], key: str, scope: Scope) -> Job:
    job = jobs.get(key)
    if job is None:
        raise SchedulerError(422, f"no installed module declares the job {key!r}")
    if not job.idempotent:
        raise SchedulerError(422, f"{key} is not declared idempotent, and delivery is at-least-once")
    if job.scope == "platform" and not scope.platform:
        raise SchedulerError(403, f"{key} is a platform job: only the super admin schedules it")
    return job


def _timing(cron: str | None, timezone: str | None, run_at: datetime | None) -> None:
    if bool(cron) == bool(run_at):
        raise SchedulerError(422, "give exactly one of cron and run_at")
    if cron:
        if not timezone:
            raise SchedulerError(422, "a cron needs an explicit timezone")
        try:
            Cron.parse(cron)
            zone(timezone)
        except CronError as e:
            raise SchedulerError(422, str(e)) from e
    elif run_at is not None and run_at.tzinfo is None:
        raise SchedulerError(422, "run_at needs a timezone offset")


def _reschedule(schedule: Schedule, now: datetime) -> None:
    if not schedule.enabled:
        schedule.next_run_at = None
    elif schedule.cron:
        schedule.next_run_at = next_window(schedule, now)
    else:
        run_at = aware(schedule.run_at, now)
        schedule.next_run_at = run_at if run_at and run_at > now else None


def create(
    db: Session, jobs: dict[str, Job], scope: Scope, config: SchedulerConfig, body: dict, actor: str
) -> Schedule:
    job = _job(jobs, body["job"], scope)
    _timing(body.get("cron"), body.get("timezone"), body.get("run_at"))
    now = utcnow()
    organisation_id = body.get("organisation_id") if scope.platform else scope.organisation_id
    schedule = Schedule(
        organisation_id=None if job.scope == "platform" else organisation_id,
        job=job.key,
        scope=job.scope,
        cron=body.get("cron"),
        timezone=body.get("timezone") if body.get("cron") else None,
        run_at=body.get("run_at"),
        arguments=dict(body.get("arguments") or {}),
        enabled=body.get("enabled", True),
        allow_overlap=body.get("allow_overlap", False),
        catch_up=body.get("catch_up") or config.default_catch_up,
        created_at=now,
    )
    if job.scope == "organisation" and not schedule.organisation_id:
        raise SchedulerError(422, f"{job.key} runs per organisation: pass organisation_id")
    _reschedule(schedule, now)
    db.add(schedule)
    db.commit()
    audit.info("schedule %s (%s) created by %s", schedule.id, schedule.job, actor)
    return schedule


def get(db: Session, scope: Scope, schedule_id: str) -> Schedule:
    schedule = db.scalar(_scoped(select(Schedule).where(Schedule.id == schedule_id), Schedule, scope))
    if schedule is None:
        raise SchedulerError(404, "no such schedule")
    return schedule


def change(db: Session, scope: Scope, schedule_id: str, changes: dict, actor: str) -> Schedule:
    schedule = get(db, scope, schedule_id)
    cron = changes.get("cron", schedule.cron)
    timezone = changes.get("timezone", schedule.timezone)
    run_at = changes.get("run_at", aware(schedule.run_at, utcnow()))
    if "cron" in changes and changes["cron"]:
        run_at = changes.get("run_at")
    if "run_at" in changes and changes["run_at"]:
        cron = changes.get("cron")
    _timing(cron, timezone, run_at)
    schedule.cron, schedule.timezone, schedule.run_at = cron, timezone if cron else None, run_at
    for key in ("enabled", "allow_overlap", "catch_up", "arguments"):
        if key in changes and changes[key] is not None:
            setattr(schedule, key, changes[key])
    _reschedule(schedule, utcnow())
    db.commit()
    audit.info("schedule %s (%s) changed by %s: %s", schedule.id, schedule.job, actor, ", ".join(sorted(changes)))
    return schedule


def remove(db: Session, scope: Scope, schedule_id: str, actor: str) -> None:
    schedule = get(db, scope, schedule_id)
    db.delete(schedule)
    db.commit()
    audit.info("schedule %s (%s) deleted by %s", schedule_id, schedule.job, actor)


def run_now(db: Session, jobs: dict[str, Job], scope: Scope, schedule_id: str, actor: str) -> Run:
    schedule = get(db, scope, schedule_id)
    _job(jobs, schedule.job, scope)
    if not schedule.allow_overlap and running_run(db, schedule) is not None:
        raise SchedulerError(409, "a run is already in progress and this schedule does not allow overlap")
    run = start_run(db, schedule, utcnow(), "manual")
    db.commit()
    audit.info("schedule %s (%s) run now by %s: run %s", schedule.id, schedule.job, actor, run.id)
    return run


def list_schedules(
    db: Session, scope: Scope, *, job: str | None, organisation_id: str | None, limit: int, offset: int
) -> tuple[list[Schedule], int]:
    q = _scoped(select(Schedule), Schedule, scope, organisation_id)
    if job:
        q = q.where(Schedule.job == job)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Schedule.job, Schedule.created_at).limit(limit).offset(offset))
    return list(rows), total


def list_runs(
    db: Session,
    scope: Scope,
    *,
    schedule_id: str | None,
    job: str | None,
    status: str | None,
    organisation_id: str | None,
    limit: int,
    offset: int,
) -> tuple[list[Run], int]:
    q = _scoped(select(Run), Run, scope, organisation_id)
    for column, value in ((Run.schedule_id, schedule_id), (Run.job, job), (Run.status, status)):
        if value:
            q = q.where(column == value)
    total = db.scalar(select(func.count()).select_from(q.subquery())) or 0
    rows = db.scalars(q.order_by(Run.started_at.desc(), Run.id.desc()).limit(limit).offset(offset))
    return list(rows), total


def get_run(db: Session, scope: Scope, run_id: str) -> Run:
    run = db.scalar(_scoped(select(Run).where(Run.id == run_id), Run, scope))
    if run is None:
        raise SchedulerError(404, "no such run")
    return run


def _iso(value: datetime | None) -> str | None:
    return aware(value, utcnow()).isoformat() if value else None


def schedule_out(s: Schedule) -> dict:
    return {
        "id": s.id,
        "organisation_id": s.organisation_id,
        "job": s.job,
        "scope": s.scope,
        "cron": s.cron,
        "timezone": s.timezone,
        "run_at": _iso(s.run_at),
        "arguments": s.arguments or {},
        "enabled": s.enabled,
        "allow_overlap": s.allow_overlap,
        "catch_up": s.catch_up,
        "created_at": _iso(s.created_at),
        "last_run_at": _iso(s.last_run_at),
        "last_status": s.last_status,
        "next_run_at": _iso(s.next_run_at),
    }


def run_out(r: Run) -> dict:
    return {
        "id": r.id,
        "schedule_id": r.schedule_id,
        "job": r.job,
        "organisation_id": r.organisation_id,
        "status": r.status,
        "trigger": r.trigger,
        "started_at": _iso(r.started_at),
        "finished_at": _iso(r.finished_at),
        "duration_ms": r.duration_ms,
        "missed_windows": r.missed_windows,
        "detail": r.detail,
    }
