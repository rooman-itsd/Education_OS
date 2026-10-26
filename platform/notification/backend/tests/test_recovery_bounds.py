"""B1: recovery failures are bounded. SQLite proves the guard logic one connection at a time; real races between
PostgreSQL connections and transaction atomicity on PostgreSQL are NOT RUN (README, PostgreSQL list)."""

import logging
from datetime import UTC, datetime, timedelta

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from eos_notification.application import messages
from eos_notification.application.messages import _defer, _Seen, recovery_delay
from eos_notification.domain.models import Message
from eos_notification.infrastructure.config import NotificationConfig
from notification_support import ScriptedTransport, outbox_events

ADDRESS = "private.person@college.example.com"


@pytest.fixture
def limits(monkeypatch):
    monkeypatch.setenv("NOTIFICATION_RECOVERY_MAX_FAILURES", "3")
    monkeypatch.setenv("NOTIFICATION_RETRY_BACKOFF_S", "10")
    monkeypatch.setenv("NOTIFICATION_RECOVERY_MAX_DELAY_S", "35")
    return NotificationConfig.from_env()


def _stuck(db, org, *, status="queued", last_error=None, attempts=0, minutes=90) -> Message:
    with organisation_scope(org.id):
        m = Message(
            organisation_id=org.id,
            template_key="billing.trial.expired",
            channel="email",
            recipient_key=ADDRESS,
            recipient_address=ADDRESS,
            variables={"organisation_name": "C"},
            body_template="Trial over for ${organisation_name}",
            subject="Your trial has ended",
            status=status,
            attempts=attempts,
            last_error=last_error,
            lease_expires_at=(datetime.now(UTC) - timedelta(minutes=1)) if status == "sending" else None,
            created_at=datetime.now(UTC) - timedelta(minutes=minutes),
        )
        db.add(m)
        db.commit()
    return m


def _poison(monkeypatch, message_id):
    real = messages.dispatch

    def flaky(db, mid, **kw):
        if mid == message_id:
            raise RuntimeError(f"bug mentioning {ADDRESS}")
        return real(db, mid, **kw)

    monkeypatch.setattr(messages, "dispatch", flaky)


def _read(db, org, message_id) -> Message:
    with organisation_scope(org.id):
        return messages.get_message(db, message_id)


def _sweep_until_terminal(db, org, message_id, max_sweeps=10):
    now = datetime.now(UTC)
    for _ in range(max_sweeps):
        messages.recover_stuck(transport=ScriptedTransport(), now=now)
        m = _read(db, org, message_id)
        if m.status == "failed":
            return m
        now = (m.next_attempt_at or m.lease_expires_at).replace(tzinfo=UTC) + timedelta(seconds=1)
    raise AssertionError("never reached failed")


# 1, 2: the limit, the preserved delivery error, one terminal outbox record ------------------------------------


def test_a_poison_message_is_failed_after_the_limit_keeping_its_delivery_error(db, org, monkeypatch, limits):
    m = _stuck(db, org, last_error="transport_unavailable")
    _poison(monkeypatch, m.id)
    final = _sweep_until_terminal(db, org, m.id)
    assert final.recovery_failures == 3 and final.last_recovery_error == "RuntimeError"
    assert final.last_error == "transport_unavailable"  # the delivery error survives
    (event,) = outbox_events(db, org.id, "notification.message.failed")
    assert event.payload["last_error"] == "recovery_exhausted" and event.payload["message_id"] == m.id
    messages.recover_stuck(transport=ScriptedTransport(), now=datetime.now(UTC) + timedelta(days=1))
    assert len(outbox_events(db, org.id, "notification.message.failed")) == 1  # terminal stays terminal


def test_without_a_delivery_error_the_message_records_recovery_exhausted(db, org, monkeypatch, limits):
    m = _stuck(db, org)
    _poison(monkeypatch, m.id)
    assert _sweep_until_terminal(db, org, m.id).last_error == "recovery_exhausted"


# 3: capped doubling delay --------------------------------------------------------------------------------------


def test_recovery_delay_doubles_and_is_capped(limits):
    assert [recovery_delay(n, limits).total_seconds() for n in range(5)] == [10, 20, 35, 35, 35]


def test_each_recorded_failure_defers_by_the_capped_delay(db, org, limits):
    m = _stuck(db, org)
    now = datetime.now(UTC)
    with SessionLocal() as s:
        for expected in (10, 20):
            with organisation_scope(org.id):
                cur = messages._get(s, org.id, m.id)
            seen = _Seen(cur.status, cur.attempts, cur.recovery_failures)
            assert _defer(SessionLocal, org.id, m.id, seen, "RuntimeError", now, limits) == "deferred"
            with organisation_scope(org.id):
                after = messages._get(s, org.id, m.id)
            assert after.next_attempt_at.replace(tzinfo=UTC) == now + timedelta(seconds=expected)
            now = after.next_attempt_at.replace(tzinfo=UTC)  # due again exactly now


# 4, 5, 6: concurrent workers ------------------------------------------------------------------------------------


def test_the_same_observed_failure_is_counted_once(db, org, limits):
    m = _stuck(db, org)
    now, seen = datetime.now(UTC), _Seen("queued", 0, 0)
    first = _defer(SessionLocal, org.id, m.id, seen, "RuntimeError", now, limits)
    second = _defer(SessionLocal, org.id, m.id, seen, "RuntimeError", now, limits)  # another worker, same view
    assert (first, second) == ("deferred", "unchanged") and _read(db, org, m.id).recovery_failures == 1


def test_two_workers_at_the_limit_publish_one_terminal_record(db, org, limits):
    m = _stuck(db, org)
    with organisation_scope(org.id), SessionLocal() as s:
        s.get(Message, m.id).recovery_failures = 2  # one failure away from the limit of 3
        s.commit()
    now, seen = datetime.now(UTC), _Seen("queued", 0, 2)
    outcomes = [_defer(SessionLocal, org.id, m.id, seen, "RuntimeError", now, limits) for _ in range(2)]
    assert outcomes == ["exhausted", "unchanged"]
    assert len(outbox_events(db, org.id, "notification.message.failed")) == 1


def test_a_newer_claim_is_never_overwritten_by_a_deferral_or_terminal_update(db, org, limits):
    m = _stuck(db, org)
    seen_before_claim = _Seen("queued", 0, 2)  # what a slow worker saw, already at the limit
    with organisation_scope(org.id), SessionLocal() as s:
        s.get(Message, m.id).recovery_failures = 2
        s.commit()
        assert messages._claim(s, org.id, m.id, datetime.now(UTC), limits)  # another worker wins the message
        s.commit()
    assert _defer(SessionLocal, org.id, m.id, seen_before_claim, "RuntimeError", datetime.now(UTC), limits) == (
        "unchanged"
    )
    after = _read(db, org, m.id)
    assert after.status == "sending" and after.attempts == 1 and after.recovery_failures == 2
    assert outbox_events(db, org.id, "notification.message.failed") == []


# 7: a sending message is deferred by its lease -------------------------------------------------------------------


def test_a_sending_message_is_deferred_by_its_lease(db, org, monkeypatch, limits):
    m = _stuck(db, org, status="sending", attempts=1)
    _poison(monkeypatch, m.id)
    now = datetime.now(UTC)
    messages.recover_stuck(transport=ScriptedTransport(), now=now)
    after = _read(db, org, m.id)
    assert after.status == "sending" and after.next_attempt_at is None
    assert after.lease_expires_at.replace(tzinfo=UTC) == now + timedelta(seconds=10)
    assert after.recovery_failures == 1 and after.attempts == 1  # recovery failures never count as provider calls


# 8: logging -------------------------------------------------------------------------------------------------------


def test_recorded_failures_log_at_most_the_limit_and_never_values(db, org, monkeypatch, limits, caplog):
    caplog.set_level(logging.DEBUG)
    m = _stuck(db, org)
    _poison(monkeypatch, m.id)
    _sweep_until_terminal(db, org, m.id)
    lines = [r.getMessage() for r in caplog.records if m.id in r.getMessage()]
    assert len(lines) == 3 and all("RuntimeError" in line for line in lines)
    assert ADDRESS not in caplog.text and "bug mentioning" not in caplog.text


def test_a_failure_to_record_is_logged_by_class_only_and_leaves_the_message_eligible(db, org, monkeypatch, caplog):
    caplog.set_level(logging.DEBUG)
    m = _stuck(db, org)
    _poison(monkeypatch, m.id)

    def database_down(*args, **kwargs):
        raise ConnectionError("could not connect: password=hunter2 host=db")

    monkeypatch.setattr(messages, "_record_recovery_failure", database_down)
    counts = messages.recover_stuck(transport=ScriptedTransport(), now=datetime.now(UTC))
    assert counts["errors"] == 1 and counts["exhausted"] == 0
    after = _read(db, org, m.id)
    assert after.recovery_failures == 0 and after.next_attempt_at is None  # still eligible next sweep
    assert "ConnectionError" in caplog.text and "hunter2" not in caplog.text and ADDRESS not in caplog.text


def test_a_stale_view_cannot_re_record_a_failure_after_the_message_is_due_again(db, org, limits):
    """Worker B records failure 1 (deferral 10 s). Worker A, slow, still holds the view from before (0 failures)
    and only acts after the deferral has passed, so the row looks eligible again. A must change nothing."""
    m = _stuck(db, org)
    now, stale = datetime.now(UTC), _Seen("queued", 0, 0)
    assert _defer(SessionLocal, org.id, m.id, stale, "RuntimeError", now, limits) == "deferred"  # worker B
    recorded = _read(db, org, m.id)
    later = now + timedelta(seconds=11)
    assert _defer(SessionLocal, org.id, m.id, stale, "ValueError", later, limits) == "unchanged"  # worker A
    after = _read(db, org, m.id)
    assert after.recovery_failures == 1 and after.last_recovery_error == "RuntimeError"
    assert after.next_attempt_at == recorded.next_attempt_at
