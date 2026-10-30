"""Billing's scheduled jobs: declared for platform/scheduler, run from scheduler.job.due, reported back with
billing.job.finished; trials past their end expire, and reminders go out 7, 3 and 1 days before the end."""

from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from eos_billing.application import consumers, jobs, service
from eos_billing.domain.models import Subscription
from eos_core.db import SessionLocal, init_db, utcnow
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import delete, select


@pytest.fixture(autouse=True)
def _db():
    init_db()
    with platform_scope(), SessionLocal() as db:
        service.seed_plans(db)
        for table in (Subscription, OutboxEvent):
            db.execute(delete(table))
        db.commit()


def _trial(ends_in: timedelta) -> str:
    org = str(uuid.uuid4())
    with organisation_scope(org), SessionLocal() as db:
        db.add(Subscription(organisation_id=org, plan_id="trial", status="trialing", trial_ends_at=utcnow() + ends_in))
        db.commit()
    return org


def _due(job: str, run_id: str = "run-1"):
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        name="scheduler.job.due",
        organisation_id=None,
        payload={"run_id": run_id, "job": job, "scope": "platform"},
    )


def _handle(event) -> None:
    with platform_scope(), SessionLocal() as db:
        consumers.on_job_due(db, event)
        db.commit()


def _events(name: str) -> list[OutboxEvent]:
    with platform_scope(), SessionLocal() as db:
        return list(db.scalars(select(OutboxEvent).where(OutboxEvent.name == name)))


def test_both_jobs_are_declared_as_idempotent_platform_jobs_with_a_daily_timing():
    assert set(jobs.JOBS) == {"billing.expire-trials", "billing.trial-reminders"}
    assert all(j["scope"] == "platform" and j["idempotent"] and j["default_cron"] for j in jobs.JOBS.values())


def test_the_expire_job_expires_only_trials_past_their_end_and_reports_back():
    ended = _trial(-timedelta(hours=1))
    running = _trial(timedelta(days=5))
    _handle(_due("billing.expire-trials"))
    with platform_scope(), SessionLocal() as db:
        status = {s.organisation_id: s.status for s in db.scalars(select(Subscription))}
    assert status == {ended: "read_only", running: "trialing"}
    assert [e.organisation_id for e in _events("billing.trial.expired")] == [ended]
    (done,) = _events("billing.job.finished")
    assert done.organisation_id is None
    assert done.payload == {"run_id": "run-1", "outcome": "succeeded", "detail": "1 trial(s) expired"}


def test_a_second_expire_run_changes_nothing():
    _trial(-timedelta(hours=1))
    _handle(_due("billing.expire-trials", "run-1"))
    _handle(_due("billing.expire-trials", "run-2"))
    assert len(_events("billing.trial.expired")) == 1


def test_reminders_go_out_seven_three_and_one_days_before_the_end_only():
    hits = {d: _trial(timedelta(days=d, hours=1)) for d in (7, 3, 1)}
    for d in (8, 5, 2, 0):
        _trial(timedelta(days=d, hours=1))
    _handle(_due("billing.trial-reminders"))
    got = {e.organisation_id: e.payload for e in _events("billing.trial.expiring")}
    assert set(got) == set(hits.values())
    for days, org in hits.items():
        assert got[org]["days_left"] == days and got[org]["organisation_id"] == org
        assert got[org]["reminder_key"] == f"{org}:{got[org]['trial_ends_on']}:{days}"
    (done,) = _events("billing.job.finished")
    assert done.payload["detail"] == "3 trial reminder(s) raised"


def test_another_modules_job_is_ignored():
    _handle(_due("fees.reminder-sweep"))
    assert _events("billing.job.finished") == []
