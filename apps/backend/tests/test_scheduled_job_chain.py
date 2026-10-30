"""The scheduled-job path across platform services, as the host composes them: scheduler fires a due schedule,
event-bus's relay hands `scheduler.job.due` to the module that owns the job, that module reports with
`<module>.job.finished`, and the relay hands the report back to scheduler, which closes the run.

The owning module here is a stand-in for billing; billing's own handler is billing's code."""

import uuid
from datetime import UTC, datetime, timedelta

from eos_core.db import SessionLocal
from eos_core.events import publish
from eos_core.tenant import get_current_organisation, is_bypass, platform_scope
from eos_event_bus.application.consumers import Consumers
from eos_event_bus.application.relay import Relay
from eos_event_bus.application.transport import InProcessTransport
from eos_event_bus.infrastructure.config import EventBusConfig
from eos_scheduler.application import jobs as jobs_module
from eos_scheduler.application.consumers import CONSUMERS as SCHEDULER_CONSUMERS
from eos_scheduler.application.jobs import Job
from eos_scheduler.application.ticker import Ticker
from eos_scheduler.domain.models import Run, Schedule
from eos_scheduler.infrastructure.config import SchedulerConfig
from sqlalchemy import select

JOB = "billing.expire-trials"


def _relay_until_quiet(relay: Relay) -> None:
    for _ in range(20):
        if relay.run_once().claimed == 0:
            return
    raise AssertionError("the outbox did not drain")


def test_a_due_platform_job_reaches_its_module_and_the_report_closes_the_run(client, monkeypatch):
    jobs = {JOB: Job.declare("billing", JOB, {"scope": "platform", "default_cron": "15 0 * * *", "idempotent": True})}
    monkeypatch.setattr(jobs_module, "discover", lambda: dict(jobs))
    handled = []
    tag = uuid.uuid4().hex[:8]

    def billing_on_job_due(db, event):
        if event.payload.get("job") != JOB or event.payload.get("arguments", {}).get("tag") != tag:
            return  # another schedule's run, left by an earlier test in the same database
        handled.append((get_current_organisation(), is_bypass(), event.payload["trigger"]))
        publish(
            db,
            "billing.job.finished",
            None,
            {"run_id": event.payload["run_id"], "outcome": "succeeded", "detail": "2 trials expired"},
        )

    now = datetime.now(UTC)
    ticker = Ticker(jobs, SchedulerConfig(), clock=lambda: now)
    with platform_scope(), SessionLocal() as db:
        db.add(
            Schedule(
                organisation_id=None,
                job=JOB,
                scope="platform",
                cron="15 0 * * *",
                timezone="UTC",
                arguments={"tag": tag},
                enabled=True,
                allow_overlap=False,
                catch_up="once",
                created_at=now,
                next_run_at=now - timedelta(seconds=1),
            )
        )
        db.commit()
    assert ticker.tick().fired >= 1

    consumers = Consumers({"billing": {"scheduler.job.due": billing_on_job_due}, "scheduler": SCHEDULER_CONSUMERS})
    _relay_until_quiet(Relay(InProcessTransport(consumers), EventBusConfig()))

    assert handled == [(None, True, "schedule")]  # a platform job runs once, in platform scope
    with platform_scope(), SessionLocal() as db:
        run = db.scalar(
            select(Run)
            .join(Schedule, Run.schedule_id == Schedule.id)
            .where(Schedule.arguments["tag"].as_string() == tag)
        )
        assert run.status == "succeeded" and run.detail == "2 trials expired"
        assert db.get(Schedule, run.schedule_id).last_status == "succeeded"


def test_billing_expire_trials_runs_end_to_end_with_the_installed_modules():
    """No stand-ins: the jobs and consumers the installed modules declare, billing's real handler."""
    from eos_billing.domain.models import Subscription
    from eos_event_bus.application.consumers import discover as discover_consumers
    from eos_scheduler.application.jobs import discover as discover_jobs

    org = str(uuid.uuid4())
    now = datetime.now(UTC)
    with platform_scope(), SessionLocal() as db:
        db.add(
            Subscription(
                organisation_id=org, plan_id="trial", status="trialing", trial_ends_at=now - timedelta(hours=1)
            )
        )
        db.commit()
    jobs = discover_jobs()
    assert {"billing.expire-trials", "billing.trial-reminders"} <= set(jobs)
    ticker = Ticker(jobs, SchedulerConfig(), clock=lambda: now)
    ticker.seed_platform_defaults()
    with platform_scope(), SessionLocal() as db:
        schedule = db.scalar(select(Schedule).where(Schedule.job == "billing.expire-trials"))
        schedule.next_run_at = now - timedelta(seconds=1)
        db.commit()
        schedule_id = schedule.id
    ticker.tick()
    _relay_until_quiet(Relay(InProcessTransport(discover_consumers()), EventBusConfig()))
    with platform_scope(), SessionLocal() as db:
        assert db.scalar(select(Subscription.status).where(Subscription.organisation_id == org)) == "read_only"
        run = db.scalar(select(Run).where(Run.schedule_id == schedule_id).order_by(Run.started_at.desc()))
        assert run.status == "succeeded" and "trial(s) expired" in run.detail
