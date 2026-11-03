"""What notification sends when the relay hands it another module's event: the right template to the
organisation's admins, once per event however often it is redelivered, and nothing at all when it cannot say
which organisation the mail is about."""

from __future__ import annotations

import logging
import tomllib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from eos_identity.domain.models import User
from eos_notification.application import consumers, jobs, organisations
from eos_notification.application import messages as messages_module
from eos_notification.domain.models import Message
from eos_notification.infrastructure import transport as transport_module
from eos_notification.infrastructure.transport import SendResult
from notification_support import Org, ScriptedTransport
from sqlalchemy import select

NAME = "Rooman Conservatory"


@pytest.fixture(autouse=True)
def _directory(monkeypatch):
    """Tenancy's lookup, as the entry point provides it in a deployment."""
    monkeypatch.setattr(organisations.hooks, "name", lambda db, organisation_id: NAME)
    transport_module.sent.clear()


def event(name: str, organisation_id: str | None, payload: dict | None = None, event_id: str | None = None):
    return SimpleNamespace(
        id=event_id or str(uuid.uuid4()), name=name, organisation_id=organisation_id, payload=payload or {}
    )


def deliver(e) -> None:
    """As the relay delivers: a session of its own, in the event's organisation."""
    scope = organisation_scope(e.organisation_id) if e.organisation_id else organisation_scope(None)
    with scope, SessionLocal() as session:
        consumers.on_event(session, e)
        session.commit()


def messages_of(organisation_id: str) -> list[Message]:
    with organisation_scope(organisation_id), SessionLocal() as session:
        return list(session.scalars(select(Message).where(Message.organisation_id == organisation_id)))


def test_every_event_notification_consumes_has_a_template_and_a_handler():
    from eos_notification.infrastructure.templates import get_default

    for name, (template, _) in consumers.EVENTS.items():
        assert consumers.CONSUMERS[name] is consumers.on_event, name
        assert get_default(template) is not None, template


def test_a_trial_reminder_reaches_the_organisation_admin_with_the_days_left():
    o = Org.create(SessionLocal())
    deliver(event("billing.trial.expiring", o.id, {"days_left": 3, "trial_ends_on": "2026-11-05"}))
    (message,) = messages_of(o.id)
    assert message.template_key == "billing.trial.reminder" and message.status == "sent"
    assert message.recipient_id == o.admin.id and message.recipient_address == o.admin.email
    assert "3 day(s)" in message.subject
    assert message.body is None  # a rendered email body is deliberately never stored
    (mail,) = [m for m in transport_module.sent if m.get("to") == o.admin.email]
    assert mail["subject"] == message.subject and NAME in mail["body"] and "2026-11-05" in mail["body"]


def test_an_expired_trial_and_an_approval_use_their_own_templates():
    o = Org.create(SessionLocal())
    deliver(event("billing.trial.expired", o.id, {"after_trial": "read_only"}))
    deliver(event("tenancy.organisation.approved", o.id, {"academy_type": "music-academy"}))
    assert {m.template_key for m in messages_of(o.id)} == {
        "billing.trial.expired",
        "tenancy.organisation.approved",
    }
    sent_to_admin = [m for m in transport_module.sent if m.get("to") == o.admin.email]
    assert len(sent_to_admin) == 2 and all(NAME in m["body"] for m in sent_to_admin)


def test_a_redelivered_event_does_not_mail_anyone_twice():
    """Delivery is at-least-once, so the same event arrives again; the client_token makes that harmless."""
    o = Org.create(SessionLocal())
    e = event("billing.trial.expired", o.id)
    deliver(e)
    deliver(e)
    (message,) = messages_of(o.id)
    assert message.client_token == f"event:{e.id}:{o.admin.id}"
    assert len([m for m in transport_module.sent if m.get("to") == o.admin.email]) == 1


def test_a_different_event_about_the_same_thing_still_sends():
    o = Org.create(SessionLocal())
    deliver(event("billing.trial.expiring", o.id, {"days_left": 7, "trial_ends_on": "2026-11-05"}))
    deliver(event("billing.trial.expiring", o.id, {"days_left": 3, "trial_ends_on": "2026-11-05"}))
    assert len(messages_of(o.id)) == 2


def test_two_trial_expiring_events_with_the_same_reminder_key_send_one_email():
    """Each run of billing.trial-reminders publishes new events with new ids, but repeated runs on the same
    day (catch-up, run now, or job firing twice) share the reminder_key and must send the reminder once."""
    o = Org.create(SessionLocal())
    e1 = event(
        "billing.trial.expiring",
        o.id,
        {"days_left": 3, "trial_ends_on": "2026-11-05", "reminder_key": f"{o.id}:2026-11-05:3"},
        event_id="event-1",
    )
    e2 = event(
        "billing.trial.expiring",
        o.id,
        {"days_left": 3, "trial_ends_on": "2026-11-05", "reminder_key": f"{o.id}:2026-11-05:3"},
        event_id="event-2",
    )
    deliver(e1)
    deliver(e2)
    (message,) = messages_of(o.id)
    assert message.client_token == f"reminder:{o.id}:2026-11-05:3:{o.admin.id}"
    assert len([m for m in transport_module.sent if m.get("to") == o.admin.email]) == 1


def test_an_unresolvable_organisation_name_raises_so_the_relay_retries(monkeypatch):
    """An unwired entry point must not produce "The trial for  has ended", and must not be marked done either:
    the relay retries a raising consumer and finally dead-letters the event, where an operator sees it."""
    monkeypatch.setattr(organisations.hooks, "name", lambda db, organisation_id: None)
    o = Org.create(SessionLocal())
    with pytest.raises(LookupError, match="no organisation name"):
        deliver(event("billing.trial.expired", o.id))
    assert messages_of(o.id) == [] and transport_module.sent == []

    # Once the lookup works again, the redelivered event sends exactly once
    monkeypatch.setattr(organisations.hooks, "name", lambda db, organisation_id: NAME)
    e = event("billing.trial.expired", o.id)
    deliver(e)
    deliver(e)
    assert [m.status for m in messages_of(o.id)] == ["sent"]


def test_an_event_of_another_organisation_never_reaches_these_admins():
    mine, theirs = Org.create(SessionLocal()), Org.create(SessionLocal())
    deliver(event("billing.trial.expired", theirs.id))
    assert messages_of(mine.id) == []
    assert [m.recipient_id for m in messages_of(theirs.id)] == [theirs.admin.id]


def test_an_event_nobody_has_a_template_for_is_ignored():
    o = Org.create(SessionLocal())
    deliver(event("billing.subscription.upgraded", o.id, {"to_plan": "pro"}))
    deliver(event("billing.trial.expired", None))  # a platform event has no organisation to mail about
    assert messages_of(o.id) == [] and transport_module.sent == []


def test_an_organisation_with_no_admin_is_logged_not_mailed(caplog):
    o = Org.create(SessionLocal())
    with organisation_scope(o.id), SessionLocal() as session:
        session.get(User, o.admin.id).status = "disabled"
        session.commit()
    with caplog.at_level(logging.WARNING, logger="eos.notification"):
        deliver(event("billing.trial.expired", o.id))
    assert messages_of(o.id) == [] and "no active admin" in caplog.text


def test_the_lookup_is_found_on_the_entry_point_group(monkeypatch):
    """How a deployment wires it: no host startup code, so the relay's own process finds it too."""
    calls = []

    def lookup(db, organisation_id):
        calls.append(organisation_id)
        return NAME

    monkeypatch.setattr(organisations, "_discover", lambda: lookup)
    organisations.reset_cache()
    try:
        with SessionLocal() as session:
            assert organisations.OrganisationHooks().name(session, "org-1") == NAME
        assert calls == ["org-1"]
    finally:
        organisations.reset_cache()


def test_an_approved_package_change_mails_the_admin_once_with_the_new_package():
    """Replaces tenancy's eos_core.notify stub, which only logged this email (#316 follow-up)."""
    o = Org.create(SessionLocal())
    e = event("tenancy.package.changed", o.id, {"organisation_id": o.id, "from": "music-academy", "to": "law-college"})
    deliver(e)
    deliver(e)  # at-least-once: a redelivery mails nobody twice
    (message,) = messages_of(o.id)
    assert message.template_key == "tenancy.package.changed" and message.status == "sent"
    assert message.recipient_id == o.admin.id and NAME in message.subject
    (mail,) = [m for m in transport_module.sent if m.get("to") == o.admin.email]
    assert "law-college" in mail["body"] and "music-academy" not in mail["body"]


def test_a_package_change_without_the_new_package_is_retried_not_mailed():
    o = Org.create(SessionLocal())
    with pytest.raises(KeyError):
        deliver(event("tenancy.package.changed", o.id, {"organisation_id": o.id, "from": "music-academy"}))
    assert messages_of(o.id) == []


# --- notification.recover-stuck: a temporarily failed email is sent by the scheduled sweep ---------------------


def job_due(job: str = "notification.recover-stuck", run_id: str | None = None):
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        name="scheduler.job.due",
        organisation_id=None,
        payload={"job": job, "run_id": run_id or str(uuid.uuid4()), "trigger": "schedule"},
    )


def run_job(e) -> None:
    """As the relay delivers a platform job: platform scope, a session of its own."""
    with platform_scope(), SessionLocal() as session:
        consumers.CONSUMERS["scheduler.job.due"](session, e)
        session.commit()


def finished_reports(run_id: str) -> list[dict]:
    with platform_scope(), SessionLocal() as session:
        rows = session.scalars(select(OutboxEvent).where(OutboxEvent.name == "notification.job.finished")).all()
        return [r.payload for r in rows if r.payload.get("run_id") == run_id]


def test_notification_declares_the_recovery_job_for_the_scheduler():
    assert jobs.JOBS["notification.recover-stuck"]["scope"] == "platform"
    assert jobs.JOBS["notification.recover-stuck"]["idempotent"] is True
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    assert pyproject["project"]["entry-points"]["eos.scheduler_jobs"] == {
        "notification": "eos_notification.application.jobs:JOBS"
    }
    assert consumers.CONSUMERS["scheduler.job.due"] is consumers.on_job_due


def test_a_transient_smtp_failure_is_sent_by_the_next_recovery_sweep(monkeypatch):
    """The audit's H1: the consumer returned normally on a retryable failure, the relay marked the event done,
    and nothing ever re-sent the queued message."""
    transport = ScriptedTransport(
        SendResult(False, reason="transport_unavailable", retryable=True), SendResult(True, "smtp-2")
    )
    monkeypatch.setattr(messages_module, "get_transport", lambda config=None: transport)
    o = Org.create(SessionLocal())

    deliver(event("tenancy.organisation.approved", o.id))
    (message,) = messages_of(o.id)
    assert message.status == "queued" and message.attempts == 1 and message.next_attempt_at is not None

    # Time passes: the retry is due
    with organisation_scope(o.id), SessionLocal() as session:
        session.get(Message, message.id).next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
        session.commit()

    e = job_due()
    run_job(e)
    (message,) = messages_of(o.id)
    assert message.status == "sent" and message.attempts == 2
    assert len(transport.sent) == 2  # one failed attempt, one delivery: no duplicate
    (report,) = finished_reports(e.payload["run_id"])
    assert report["outcome"] == "succeeded" and "redriven 1" in report["detail"]

    # The next sweep finds nothing to do and sends nothing again
    run_job(job_due())
    assert len(transport.sent) == 2


def test_a_message_not_yet_due_is_left_for_a_later_sweep(monkeypatch):
    transport = ScriptedTransport(SendResult(False, reason="throttled", retryable=True), SendResult(True, "ok"))
    monkeypatch.setattr(messages_module, "get_transport", lambda config=None: transport)
    o = Org.create(SessionLocal())
    deliver(event("billing.trial.expired", o.id))
    run_job(job_due())
    (message,) = messages_of(o.id)
    assert message.status == "queued" and len(transport.sent) == 1


def test_the_recovery_job_ignores_other_modules_jobs():
    e = job_due(job="billing.expire-trials")
    run_job(e)
    assert finished_reports(e.payload["run_id"]) == []


def test_a_failed_sweep_is_reported_to_the_run_not_raised(monkeypatch):
    def boom():
        raise RuntimeError("database unavailable for user someone@example.com")

    monkeypatch.setattr(messages_module, "recover_stuck", boom)
    e = job_due()
    run_job(e)  # does not raise: the next tick runs the sweep again
    (report,) = finished_reports(e.payload["run_id"])
    assert report == {"run_id": e.payload["run_id"], "outcome": "failed", "detail": "RuntimeError"}
