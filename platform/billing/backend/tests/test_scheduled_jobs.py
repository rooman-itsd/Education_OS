"""Billing's scheduled jobs: declared for platform/scheduler, run from scheduler.job.due, reported back with
billing.job.finished; trials past their end expire, and reminders go out 7, 3 and 1 days before the end."""

from __future__ import annotations

import uuid
from datetime import timedelta
from types import SimpleNamespace

import pytest
from eos_billing.application import consumers, jobs, service
from eos_billing.domain.models import Subscription, TrialReminder
from eos_core.db import SessionLocal, init_db, utcnow
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import delete, select


@pytest.fixture(autouse=True)
def _db():
    init_db()
    with platform_scope(), SessionLocal() as db:
        service.seed_plans(db)
        for table in (TrialReminder, Subscription, OutboxEvent):
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


def test_reminders_go_out_seven_three_and_one_days_before_the_end():
    hits = {d: _trial(timedelta(days=d, hours=1)) for d in (7, 3, 1)}
    for d in (8, 0):
        _trial(timedelta(days=d, hours=1))  # too early, and already ended
    _handle(_due("billing.trial-reminders"))
    got = {e.organisation_id: e.payload for e in _events("billing.trial.expiring")}
    assert set(got) == set(hits.values())
    for days, org in hits.items():
        assert got[org]["days_left"] == days and got[org]["threshold"] == days and got[org]["organisation_id"] == org
        assert got[org]["reminder_key"] == f"{org}:{got[org]['trial_ends_on']}:{days}"
    (done,) = _events("billing.job.finished")
    assert done.payload["detail"] == "3 trial reminder(s) raised"


def test_another_modules_job_is_ignored():
    _handle(_due("fees.reminder-sweep"))
    assert _events("billing.job.finished") == []


# --- missed reminders are caught up, never raised twice (#316 audit, F4) ----------------------------------------


def _reminders_for(org: str) -> list[dict]:
    return [e.payload for e in _events("billing.trial.expiring") if e.organisation_id == org]


def _run() -> None:
    _handle(_due("billing.trial-reminders", run_id=str(uuid.uuid4())))


def test_the_due_threshold_for_each_day():
    assert [service.due_threshold(d) for d in (9, 8, 7, 6, 5, 4, 3, 2, 1, 0, -1)] == [
        None, None, 7, 7, 7, 7, 3, 3, 1, None, None,
    ]  # fmt: skip


def test_a_three_day_reminder_missed_on_its_day_goes_out_the_next_day_once():
    """The audit's case: the scheduler was down on the day the trial had 3 days left."""
    org = _trial(timedelta(days=2, hours=1))
    _run()
    _run()  # the same day again (a retry, or a catch-up window): nothing new
    (reminder,) = _reminders_for(org)
    assert (reminder["threshold"], reminder["days_left"]) == (3, 2)
    assert reminder["reminder_key"] == f"{org}:{reminder['trial_ends_on']}:3"


def test_a_missed_seven_day_reminder_is_raised_once_until_the_three_day_one_is_due(monkeypatch):
    org = _trial(timedelta(days=5, hours=1))
    _run()
    assert [r["threshold"] for r in _reminders_for(org)] == [7]
    # a day later (4 left): still the 7-day window, already raised
    monkeypatch.setattr(service, "utcnow", lambda: utcnow() + timedelta(days=1))
    _run()
    assert [r["threshold"] for r in _reminders_for(org)] == [7]
    # two days later (3 left): the 3-day reminder
    monkeypatch.setattr(service, "utcnow", lambda: utcnow() + timedelta(days=2))
    _run()
    assert [r["threshold"] for r in _reminders_for(org)] == [7, 3]


def test_a_superseded_reminder_is_not_sent_late():
    """Down for the 7- and 3-day windows: only the 1-day reminder goes out, not three at once."""
    org = _trial(timedelta(days=1, hours=1))
    _run()
    assert [r["threshold"] for r in _reminders_for(org)] == [1]


def test_a_reminder_recorded_by_a_concurrent_run_is_not_raised_again():
    org = _trial(timedelta(days=3, hours=1))
    ends_on = (utcnow() + timedelta(days=3, hours=1)).date().isoformat()
    with organisation_scope(org), SessionLocal() as db:  # the other run committed first
        db.add(TrialReminder(organisation_id=org, trial_ends_on=ends_on, threshold=3, days_left=3))
        db.commit()
    _run()
    assert _reminders_for(org) == []
    (done,) = [e for e in _events("billing.job.finished")]
    assert done.payload["detail"] == "0 trial reminder(s) raised"


def test_trial_dates_are_counted_in_utc_whatever_offset_the_database_returns():
    """PostgreSQL returns timestamptz in the session's time zone, SQLite returns it naive (stored as UTC). 01:30 on
    the 3rd at +05:30 is 20:00 on the 2nd in UTC: the reminder must count from the 2nd."""
    from datetime import UTC, datetime, timezone

    india = timezone(timedelta(hours=5, minutes=30))
    assert service._utc(datetime(2026, 11, 3, 1, 30, tzinfo=india)).date().isoformat() == "2026-11-02"
    assert service._utc(datetime(2026, 11, 3, 1, 30)) == datetime(2026, 11, 3, 1, 30, tzinfo=UTC)
