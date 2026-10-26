"""Regression tests for review findings 1-5 (second review). Each one failed before its fix. SQLite only: they prove
the guard logic, not PostgreSQL row-level security, rollback or real multi-worker concurrency."""

import logging
import traceback
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from eos_notification.application import messages
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure.config import NotificationConfig
from notification_support import NOW, ScriptedTransport, later, outbox_events, reminder_request, verify_request
from sqlalchemy import select

EXPIRED = {"template": "billing.trial.expired", "variables": {"organisation_name": "C"}}


def send(db, org, as_org, **request):
    with as_org(org):
        return messages.send_message(db, now=NOW, **request)


# --- Finding 1: an event-linked request must name its channel -------------------------------------------------


def test_an_event_linked_request_without_a_channel_is_a_422(db, org, as_org):
    with as_org(org), pytest.raises(NotificationError) as e:
        messages.accept_message(db, recipient={"user_id": org.member.id}, source_event_id=str(uuid.uuid4()), **EXPIRED)
    assert e.value.status == 422 and "channel" in e.value.detail


@pytest.mark.parametrize("order", [("in_app", "email"), ("email", "in_app")])
def test_one_event_can_produce_a_message_on_each_channel_in_either_order(db, org, as_org, order):
    event = str(uuid.uuid4())
    with as_org(org):
        for channel in order:
            accepted = messages.accept_message(
                db, recipient={"user_id": org.member.id}, source_event_id=event, channel=channel, **EXPIRED
            )
            db.commit()
            assert accepted.created and accepted.message.channel == channel
        rows = db.scalars(select(Message).where(Message.source_event_id == event)).all()
    assert sorted(r.channel for r in rows) == ["email", "in_app"]


# --- Finding 2: equivalent requests share a fingerprint; different ones do not -----------------------------------


def test_omitted_and_explicit_equivalent_category_are_the_same_request(db, org, as_org):
    request = reminder_request(client_token="cat")
    first, _ = send(db, org, as_org, **request)
    again, created = send(db, org, as_org, **{**request, "category": "reminder"})
    assert not created and again.id == first.id


def test_missing_and_empty_locale_are_the_same_request(db, org, as_org):
    request = reminder_request(user_id=org.member.id, client_token="loc")
    first, _ = send(db, org, as_org, **request)
    retry = {**request, "recipient": {"user_id": org.member.id, "locale": ""}}
    again, created = send(db, org, as_org, **retry)
    assert not created and again.id == first.id


def test_a_genuinely_different_locale_is_still_a_different_request(db, org, as_org):
    request = reminder_request(user_id=org.member.id, client_token="loc2")
    send(db, org, as_org, **request)
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **{**request, "recipient": {"user_id": org.member.id, "locale": "hi"}})
    assert e.value.status == 422


def test_omitted_and_explicit_channel_stay_distinct_requests_as_intended(db, org, as_org):
    """An omitted channel means "let preferences decide", which is not the same request as naming one."""
    request = reminder_request(client_token="chan")
    send(db, org, as_org, **request)
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **{**request, "channel": "email"})
    assert e.value.status == 422


# --- Finding 3: a poison row cannot block recovery ----------------------------------------------------------


def _stuck(db, org, minutes: int) -> Message:
    with organisation_scope(org.id):
        m = Message(
            organisation_id=org.id,
            template_key="billing.trial.expired",
            channel="email",
            recipient_key="p@college.example.com",
            recipient_address="p@college.example.com",
            variables={"organisation_name": "C"},
            body_template="Trial over for ${organisation_name}",
            subject="Your trial has ended",
            status="queued",
            created_at=datetime.now(UTC) - timedelta(minutes=minutes),
        )
        db.add(m)
        db.commit()
    return m


def test_a_poison_row_is_deferred_so_the_next_row_is_reached_on_the_next_sweep(db, org, as_org, monkeypatch):
    poison = _stuck(db, org, minutes=90)
    good = _stuck(db, org, minutes=60)
    real = messages.dispatch

    def flaky(db, message_id, **kw):
        if message_id == poison.id:
            raise RuntimeError("bug")
        return real(db, message_id, **kw)

    monkeypatch.setattr(messages, "dispatch", flaky)
    now = datetime.now(UTC)
    first = messages.recover_stuck(transport=ScriptedTransport(), now=now, limit=1)
    assert first["errors"] == 1 and first["redriven"] == 0  # a failure is never counted as processed
    second = messages.recover_stuck(transport=ScriptedTransport(), now=now + timedelta(seconds=1), limit=1)
    assert second["redriven"] == 1
    with as_org(org):
        p, g = messages.get_message(db, poison.id), messages.get_message(db, good.id)
    assert g.status == "sent"
    assert p.status == "queued" and p.attempts == 0 and p.last_error is None  # the delivery error is not touched
    assert p.recovery_failures == 1 and p.last_recovery_error == "RuntimeError"
    assert p.next_attempt_at.replace(tzinfo=UTC) > now  # deferred, and picked up again once due


def test_deferring_a_failed_row_never_overwrites_another_workers_newer_claim(db, org, as_org, monkeypatch):
    m = _stuck(db, org, minutes=90)
    now = datetime.now(UTC)

    def claimed_elsewhere_then_crash(db, org_id, message_id, *args):
        with organisation_scope(org_id), SessionLocal() as other:  # a second worker wins the row meanwhile
            assert messages._claim(other, org_id, message_id, now, NotificationConfig.from_env())
            other.commit()
        raise RuntimeError("this worker fails after losing the race")

    monkeypatch.setattr(messages, "_recover_one", claimed_elsewhere_then_crash)
    assert messages.recover_stuck(transport=ScriptedTransport(), now=now)["errors"] == 1
    with as_org(org):
        after = messages.get_message(db, m.id)
    assert after.status == "sending" and after.attempts == 1 and after.next_attempt_at is None
    assert after.last_error is None and after.recovery_failures == 0  # the other worker's state is untouched


# --- Finding 4: a stale dispatch cannot fail a message another worker reclaimed -------------------------------


def test_a_stale_dispatch_cannot_fail_a_secret_bearing_message_reclaimed_meanwhile(db, org, as_org, monkeypatch):
    with as_org(org):
        accepted = messages.accept_message(db, now=NOW, **verify_request())
        db.commit()
        config = NotificationConfig.from_env()
        assert messages._claim(db, org.id, accepted.message.id, NOW, config)  # attempt 1, then that worker stalls
        db.commit()
    real_get_default = messages.get_default

    def reclaim_between_read_and_write(key):  # runs right after dispatch read the (now stale) row
        with organisation_scope(org.id), SessionLocal() as other:
            assert messages._claim(other, org.id, accepted.message.id, later(500), config)  # attempt 2
            other.commit()
        return real_get_default(key)

    monkeypatch.setattr(messages, "get_default", reclaim_between_read_and_write)
    with as_org(org):
        out = messages.dispatch(db, accepted.message.id, now=later(500))  # no secrets: the stale view says "fail it"
    assert out.status == "sending" and out.attempts == 2
    assert outbox_events(db, org.id, "notification.message.failed") == []


# --- Finding 5: a database error never carries row values into errors or logs ---------------------------------


def test_an_unexplained_integrity_error_exposes_no_row_values(db, org, as_org, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    address = "private.person@college.example.com"
    request = reminder_request(client_token="clash", recipient={"address": address})
    send(db, org, as_org, **request)
    # Make every lookup miss, so the second insert hits the unique constraint and no duplicate can be found.
    monkeypatch.setattr(messages, "scoped", lambda db, query, model: query.where(False))
    with as_org(org), pytest.raises(NotificationError) as e:
        messages.accept_message(db, now=NOW, **request)
    db.rollback()
    text = "".join(traceback.format_exception(e.value))
    assert e.value.status == 500
    assert address not in text and "parameters" not in text and "College" not in text
    assert address not in caplog.text and "parameters" not in caplog.text
