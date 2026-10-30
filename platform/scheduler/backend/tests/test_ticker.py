"""The tick: firing, catch-up, overlap, timeouts, and closing a run from the owning module's report."""

from __future__ import annotations

import uuid
from datetime import timedelta

from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope, platform_scope
from eos_scheduler.application.consumers import CONSUMERS, on_job_finished
from eos_scheduler.domain.models import Schedule
from scheduler_support import NOW, Clock, add_schedule, events, finished, runs, schedule, ticker
from sqlalchemy import select

ORG = str(uuid.uuid4())


def _report(event):
    scope = organisation_scope(event.organisation_id) if event.organisation_id else platform_scope()
    with scope, SessionLocal() as db:
        on_job_finished(db, event)
        db.commit()


def test_platform_jobs_with_a_default_timing_get_a_utc_schedule_once():
    clock = Clock()
    t = ticker(clock)
    assert t.seed_platform_defaults() == 1 and t.seed_platform_defaults() == 0
    with platform_scope(), SessionLocal() as db:
        (s,) = db.scalars(select(Schedule))
    assert (s.job, s.scope, s.organisation_id, s.cron, s.timezone) == (
        "billing.expire-trials",
        "platform",
        None,
        "15 0 * * *",
        "UTC",
    )
    assert s.next_run_at.replace(tzinfo=NOW.tzinfo) == NOW.replace(day=30, hour=0, minute=15)


def test_a_due_schedule_starts_a_run_and_hands_the_job_to_its_module():
    sid = add_schedule("billing.expire-trials", arguments={"dry_run": False})
    result = ticker(Clock()).tick()
    assert result.fired == 1
    (run,) = runs(sid)
    assert run.status == "running" and run.trigger == "schedule" and run.missed_windows == 0
    (due,) = events("scheduler.job.due")
    assert due.organisation_id is None
    assert due.payload == {
        "run_id": run.id,
        "schedule_id": sid,
        "job": "billing.expire-trials",
        "scope": "platform",
        "trigger": "schedule",
        "arguments": {"dry_run": False},
        "missed_windows": 0,
    }
    s = schedule(sid)
    assert s.last_status == "running" and s.next_run_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(hours=1)


def test_an_organisation_schedule_publishes_in_its_organisation():
    add_schedule("fees.reminder-sweep", ORG)
    ticker(Clock()).tick()
    (due,) = events("scheduler.job.due")
    assert due.organisation_id == ORG and due.payload["scope"] == "organisation"


def test_nothing_fires_before_its_window_or_while_disabled():
    add_schedule("billing.expire-trials", next_run_at=NOW + timedelta(minutes=1))
    add_schedule("fees.reminder-sweep", ORG, enabled=False)
    assert ticker(Clock()).tick().fired == 0 and runs() == []


def test_missed_windows_run_once_with_the_count_recorded():
    sid = add_schedule("billing.expire-trials", next_run_at=NOW - timedelta(hours=3))  # hourly: 09, 10, 11, 12
    ticker(Clock()).tick()
    (run,) = runs(sid)
    assert run.trigger == "catch_up" and run.missed_windows == 3


def test_catch_up_never_skips_missed_windows_but_keeps_the_schedule_going():
    sid = add_schedule("billing.expire-trials", next_run_at=NOW - timedelta(hours=3), catch_up="never")
    assert ticker(Clock()).tick().skipped == 1 and runs(sid) == []
    assert schedule(sid).next_run_at.replace(tzinfo=NOW.tzinfo) == NOW + timedelta(hours=1)


def test_windows_older_than_the_horizon_are_not_run():
    sid = add_schedule("billing.expire-trials", cron="0 0 1 1 *", next_run_at=NOW - timedelta(days=300))
    ticker(Clock(), catch_up_horizon_s=86_400).tick()
    assert runs(sid) == []


def test_overlap_is_refused_and_announced():
    clock = Clock()
    sid = add_schedule("billing.expire-trials")
    t = ticker(clock, run_timeout_s=86_400)
    t.tick()
    clock.advance(hours=1)
    assert t.tick().skipped == 1
    first, second = runs(sid)
    assert first.status == "running" and second.status == "skipped"
    (skipped,) = events("scheduler.run.skipped")
    assert skipped.payload["reason"] == "overlap" and skipped.payload["schedule_id"] == sid


def test_a_job_no_installed_module_declares_fails_the_run_visibly():
    sid = add_schedule("lms.gone-job")
    ticker(Clock()).tick()
    (run,) = runs(sid)
    assert run.status == "failed" and "no installed module" in run.detail
    assert [e.payload["job"] for e in events("scheduler.run.failed")] == ["lms.gone-job"]


def test_a_non_idempotent_job_is_never_fired():
    sid = add_schedule("fees.unsafe", ORG)
    ticker(Clock()).tick()
    assert [r.status for r in runs(sid)] == ["failed"] and events("scheduler.job.due") == []


def test_the_module_report_closes_the_run_once():
    clock = Clock()
    sid = add_schedule("billing.expire-trials")
    ticker(clock).tick()
    (run,) = runs(sid)
    _report(finished(run.id, "succeeded", "3 trials expired"))
    _report(finished(run.id, "failed", "a redelivery must not reopen it"))
    (run,) = runs(sid)
    assert run.status == "succeeded" and run.detail == "3 trials expired" and run.finished_at is not None
    assert schedule(sid).last_status == "succeeded"
    (ok,) = events("scheduler.run.succeeded")
    assert ok.payload["run_id"] == run.id and "duration_ms" in ok.payload


def test_another_module_cannot_close_a_run():
    sid = add_schedule("billing.expire-trials")
    ticker(Clock()).tick()
    (run,) = runs(sid)
    _report(finished(run.id, "failed", "not mine", module="fees"))
    _report(finished(run.id, "nonsense", module="fees"))
    assert runs(sid)[0].status == "running"


def test_an_unknown_outcome_from_the_owner_fails_the_run():
    sid = add_schedule("billing.expire-trials")
    ticker(Clock()).tick()
    _report(finished(runs(sid)[0].id, "maybe"))
    assert runs(sid)[0].status == "failed"


def test_a_run_nobody_closes_fails_after_the_timeout():
    clock = Clock()
    sid = add_schedule("billing.expire-trials", allow_overlap=True)
    t = ticker(clock, run_timeout_s=600)
    t.tick()
    clock.advance(minutes=11)
    assert t.tick().timed_out == 1
    run = runs(sid)[0]
    assert run.status == "failed" and "within 600 s" in run.detail
    assert [e.payload["run_id"] for e in events("scheduler.run.failed")] == [run.id]


def test_a_one_off_fires_once():
    sid = add_schedule("billing.expire-trials", cron=None, timezone=None, run_at=NOW, next_run_at=NOW)
    t = ticker(Clock())
    assert t.tick().fired == 1 and t.tick().fired == 0
    assert schedule(sid).next_run_at is None


def test_the_consumer_mapping_covers_every_module_with_a_job(monkeypatch):
    from eos_scheduler.application import jobs as jobs_module

    monkeypatch.setattr(jobs_module, "discover", lambda: dict(__import__("scheduler_support").JOBS))
    assert dict(CONSUMERS) == {"billing.job.finished": on_job_finished, "fees.job.finished": on_job_finished}


def test_prune_keeps_running_runs_and_recent_history():
    clock = Clock()
    old = add_schedule("billing.expire-trials", allow_overlap=True)
    t = ticker(clock, run_retention_days=30, run_timeout_s=86_400)
    t.tick()
    _report(finished(runs(old)[0].id))
    clock.advance(days=31)
    add_schedule("fees.reminder-sweep", ORG, next_run_at=clock.now)
    t.tick()
    first = runs(old)[0].id
    assert t.prune() == 1
    left = runs()
    assert first not in [r.id for r in left]  # finished 31 days ago: gone
    assert left and all(r.started_at.replace(tzinfo=NOW.tzinfo) == clock.now for r in left)  # today's stay
