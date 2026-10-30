"""Helpers shared by the scheduler tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.application.service import create_user
from eos_scheduler.application.jobs import Job
from eos_scheduler.application.ticker import Ticker
from eos_scheduler.domain.models import Run, Schedule
from eos_scheduler.infrastructure.config import SchedulerConfig
from sqlalchemy import select

NOW = datetime(2026, 10, 29, 12, 0, tzinfo=UTC)

JOBS = {
    "billing.expire-trials": Job.declare(
        "billing", "billing.expire-trials", {"scope": "platform", "default_cron": "15 0 * * *", "idempotent": True}
    ),
    "fees.reminder-sweep": Job.declare("fees", "fees.reminder-sweep", {"scope": "organisation", "idempotent": True}),
    "fees.unsafe": Job.declare("fees", "fees.unsafe", {"scope": "organisation", "idempotent": False}),
}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Clock:
    def __init__(self, now: datetime = NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


def ticker(clock: Clock, jobs: dict | None = None, **settings) -> Ticker:
    return Ticker(JOBS if jobs is None else jobs, SchedulerConfig(**settings), clock=clock)


def add_schedule(job: str, organisation_id: str | None = None, *, next_run_at: datetime = NOW, **fields) -> str:
    scope = organisation_scope(organisation_id) if organisation_id else platform_scope()
    with scope, SessionLocal() as db:
        s = Schedule(
            organisation_id=organisation_id,
            job=job,
            scope="organisation" if organisation_id else "platform",
            cron=fields.pop("cron", "0 * * * *"),
            timezone=fields.pop("timezone", "UTC"),
            arguments=fields.pop("arguments", {}),
            enabled=fields.pop("enabled", True),
            allow_overlap=fields.pop("allow_overlap", False),
            catch_up=fields.pop("catch_up", "once"),
            created_at=NOW - timedelta(days=1),
            next_run_at=next_run_at,
            **fields,
        )
        db.add(s)
        db.commit()
        return s.id


def runs(schedule_id: str | None = None) -> list[Run]:
    with platform_scope(), SessionLocal() as db:
        q = select(Run).order_by(Run.started_at, Run.id)
        if schedule_id:
            q = q.where(Run.schedule_id == schedule_id)
        return list(db.scalars(q))


def schedule(schedule_id: str) -> Schedule:
    with platform_scope(), SessionLocal() as db:
        return db.get(Schedule, schedule_id)


def events(name: str) -> list[OutboxEvent]:
    with platform_scope(), SessionLocal() as db:
        return list(db.scalars(select(OutboxEvent).where(OutboxEvent.name == name).order_by(OutboxEvent.occurred_at)))


def finished(run_id: str, outcome: str = "succeeded", detail: str = "done", module: str = "billing", org=None):
    """What the relay hands scheduler when the owning module reports back."""
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        name=f"{module}.job.finished",
        organisation_id=org,
        payload={"run_id": run_id, "outcome": outcome, "detail": detail},
    )


class Org:
    def __init__(self):
        self.id = str(uuid.uuid4())
        with organisation_scope(self.id), SessionLocal() as db:
            self.admin = self._user(db, ["org-admin"])
            self.member = self._user(db, ["student"])

    def _user(self, db, roles):
        u = create_user(
            db,
            organisation_id=self.id,
            email=f"u-{uuid.uuid4().hex[:8]}@example.com",
            name="U",
            password="Secret123!",
            roles=roles,
        )
        db.commit()
        return u

    def headers(self, user) -> dict:
        return auth(create_token(user_id=user.id, organisation_id=self.id, roles=list(user.roles)))


def super_admin_headers() -> dict:
    with platform_scope(), SessionLocal() as db:
        u = create_user(
            db,
            organisation_id=None,
            email=f"root-{uuid.uuid4().hex[:8]}@platform.example.com",
            name="Root",
            password="Secret123!",
            roles=["super-admin"],
            is_super_admin=True,
        )
        db.commit()
    return auth(create_token(user_id=u.id, organisation_id=None, roles=["super-admin"], super_admin=True))
