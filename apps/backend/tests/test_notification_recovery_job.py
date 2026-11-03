"""A temporarily failed email is sent, end to end with the installed modules (#316 follow-up).

The approval email's first SMTP attempt fails with a retryable error. Before this job existed, the message stayed
`queued` forever: the consumer returned normally, the relay marked the event done, and nothing called
`recover_stuck()`. Now scheduler fires `notification.recover-stuck` (declared on notification's
`eos.scheduler_jobs` entry point), the relay hands the due event to notification, the sweep re-sends the message,
and notification's report closes the run. Only the SMTP transport is scripted; every other link is the deployment's
own wiring."""

import uuid
from datetime import UTC, datetime, timedelta

from eos_core.db import SessionLocal
from eos_core.events import publish
from eos_core.tenant import organisation_scope, platform_scope
from eos_event_bus.application.consumers import discover as discover_consumers
from eos_event_bus.application.relay import Relay
from eos_event_bus.application.transport import InProcessTransport
from eos_event_bus.infrastructure.config import EventBusConfig
from eos_identity.application.service import create_user
from eos_notification.application import messages, organisations
from eos_notification.domain.models import Message
from eos_notification.infrastructure.transport import SendResult
from eos_scheduler.application.jobs import discover as discover_jobs
from eos_scheduler.application.ticker import Ticker
from eos_scheduler.domain.models import Run, Schedule
from eos_scheduler.infrastructure.config import SchedulerConfig
from eos_tenancy.domain.models import Organisation
from sqlalchemy import select

JOB = "notification.recover-stuck"


class FlakySmtp:
    """Refuses the first send with a retryable error (an SMTP 4xx), accepts every later one."""

    def __init__(self):
        self.calls = []

    def send(self, message):
        self.calls.append(message)
        if len(self.calls) == 1:
            return SendResult(False, reason="transport_unavailable", retryable=True)
        return SendResult(True, provider_message_id=f"smtp-{len(self.calls)}")


def _organisation_with_admin() -> str:
    with platform_scope(), SessionLocal() as db:
        org = Organisation(
            name="Harmony School of Music",
            slug=f"retry-{uuid.uuid4().hex[:8]}",
            academy_type="music-academy",
            status="active",
        )
        db.add(org)
        db.commit()
        organisation_id = org.id
    with organisation_scope(organisation_id), SessionLocal() as db:
        create_user(
            db,
            organisation_id=organisation_id,
            email=f"admin-{uuid.uuid4().hex[:8]}@harmony.example.com",
            name="Admin",
            password="Passw0rd!x",
            roles=["org-admin"],
        )
        db.commit()
    return organisation_id


def _drain(relay: Relay) -> None:
    for _ in range(20):
        if relay.run_once().claimed == 0:
            return
    raise AssertionError("the outbox did not drain")


def test_the_recovery_job_is_declared_by_the_installed_notification_module():
    job = discover_jobs()[JOB]
    assert job.module == "notification" and job.scope == "platform"


def test_an_approval_email_that_failed_once_is_sent_by_the_scheduled_sweep(client, monkeypatch):
    organisations.reset_cache()
    smtp = FlakySmtp()
    monkeypatch.setattr(messages, "get_transport", lambda config=None: smtp)
    organisation_id = _organisation_with_admin()
    relay = Relay(InProcessTransport(discover_consumers()), EventBusConfig())

    # Tenancy approves the organisation; the relay hands the event to notification; SMTP refuses it once
    with organisation_scope(organisation_id), SessionLocal() as db:
        publish(db, "tenancy.organisation.approved", organisation_id, {"academy_type": "music-academy"})
        db.commit()
    _drain(relay)
    with organisation_scope(organisation_id), SessionLocal() as db:
        (message,) = db.scalars(select(Message).where(Message.organisation_id == organisation_id)).all()
        assert message.status == "queued" and message.template_key == "tenancy.organisation.approved"
        message.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)  # the retry is due
        db.commit()
        message_id = message.id

    # The scheduler's platform default fires; the relay delivers the due job to notification's sweep
    now = datetime.now(UTC)
    jobs = discover_jobs()
    ticker = Ticker(jobs, SchedulerConfig(), clock=lambda: now)
    ticker.seed_platform_defaults()
    with platform_scope(), SessionLocal() as db:
        schedule = db.scalar(select(Schedule).where(Schedule.job == JOB))
        assert schedule.cron == "*/5 * * * *"
        schedule.next_run_at = now - timedelta(seconds=1)
        db.commit()
        schedule_id = schedule.id
    assert ticker.tick().fired >= 1
    _drain(relay)

    with organisation_scope(organisation_id), SessionLocal() as db:
        message = db.get(Message, message_id)
        assert message.status == "sent" and message.attempts == 2
    assert len(smtp.calls) == 2  # one refused attempt, one delivery
    with platform_scope(), SessionLocal() as db:
        run = db.scalar(select(Run).where(Run.schedule_id == schedule_id).order_by(Run.started_at.desc()))
        assert run.status == "succeeded" and "redriven 1" in run.detail
