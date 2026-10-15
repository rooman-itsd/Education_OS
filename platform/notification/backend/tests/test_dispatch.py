"""Retry, claim, fencing and recovery logic. SQLite runs one writer at a time, so these prove the guarded-UPDATE
LOGIC (a second claim or a stale result changes nothing). They do NOT prove behaviour under real concurrent
connections: that is on the NOT RUN PostgreSQL list."""

from datetime import UTC, datetime, timedelta

import pytest
from eos_notification.application import messages, preferences
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure.config import NotificationConfig
from eos_notification.infrastructure.templates import get_default
from eos_notification.infrastructure.transport import SendResult
from notification_support import (
    NOW,
    ScriptedTransport,
    later,
    outbox_events,
    outbox_names,
    reminder_request,
    verify_request,
)

RETRYABLE = SendResult(False, reason="transport_unavailable", retryable=True)
OK = SendResult(True, "provider-1")


def accept(db, org, as_org, **request) -> Message:
    with as_org(org):
        accepted = messages.accept_message(db, now=NOW, **request)
        db.commit()
    return accepted.message


def fresh(db, org, as_org, message_id) -> Message:
    with as_org(org):
        return messages.get_message(db, message_id)


def sweep(transport, now, **kw):
    return messages.recover_stuck(transport=transport, now=now, **kw)


def real_future(seconds: float) -> datetime:
    """created_at comes from the real clock, so "never dispatched for a while" needs a real-clock base."""
    return datetime.now(UTC) + timedelta(seconds=seconds)


def test_a_retryable_failure_is_requeued_with_a_backoff_and_no_failure_event(db, org, as_org):
    t = ScriptedTransport(RETRYABLE, OK)
    with as_org(org):
        m, _ = messages.send_message(db, transport=t, now=NOW, **reminder_request())
    assert m.status == "queued" and m.attempts == 1 and m.last_error == "transport_unavailable"
    assert aware_eq(m.next_attempt_at, later(30)) and "notification.message.failed" not in outbox_names(db, org.id)

    assert sweep(t, later(10))["found"] == 0  # backoff has not elapsed
    assert sweep(t, later(31))["redriven"] == 1
    m = fresh(db, org, as_org, m.id)
    assert m.status == "sent" and m.attempts == 2 and m.last_error is None and len(t.sent) == 2


def aware_eq(a, b):
    return a.replace(tzinfo=UTC) == b


def test_attempts_are_bounded_and_the_failure_event_is_raised_once(db, org, as_org, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_MAX_ATTEMPTS", "3")
    t = ScriptedTransport(RETRYABLE)
    with as_org(org):
        m, _ = messages.send_message(db, transport=t, now=NOW, **reminder_request())
    sweep(t, later(31))
    sweep(t, later(200))
    sweep(t, later(10_000))  # nothing left to do
    m = fresh(db, org, as_org, m.id)
    assert m.status == "failed" and m.attempts == 3 and len(t.sent) == 3
    (event,) = outbox_events(db, org.id, "notification.message.failed")
    assert event.payload["attempts"] == 3 and event.payload["last_error"] == "transport_unavailable"


def test_a_non_retryable_failure_is_final_immediately(db, org, as_org):
    t = ScriptedTransport(SendResult(False, reason="rejected", retryable=False))
    with as_org(org):
        m, _ = messages.send_message(db, transport=t, now=NOW, **reminder_request())
    assert (
        m.status == "failed" and m.attempts == 1 and len(outbox_events(db, org.id, "notification.message.failed")) == 1
    )


def test_provider_text_is_never_stored_only_a_stable_code(db, org, as_org):
    t = ScriptedTransport(SendResult(False, reason="mailbox bob@private.example full", retryable=False))
    with as_org(org):
        m, _ = messages.send_message(db, transport=t, now=NOW, **reminder_request())
    assert m.last_error == "rejected" and "bob" not in m.last_error


def test_a_transport_exception_counts_as_a_retryable_attempt(db, org, as_org):
    t = ScriptedTransport(RuntimeError("boom bob@private.example"))
    with as_org(org):
        m, _ = messages.send_message(db, transport=t, now=NOW, **reminder_request())
    assert m.status == "queued" and m.last_error == "transport_error"


def test_a_secret_bearing_message_is_not_retried_because_its_secret_is_gone(db, org, as_org):
    t = ScriptedTransport(RETRYABLE, OK)
    with as_org(org):
        m, _ = messages.send_message(db, transport=t, now=NOW, **verify_request())
    assert m.status == "failed" and m.last_error == "transport_unavailable" and len(t.sent) == 1
    sweep(t, later(10_000))
    assert len(t.sent) == 1  # never re-sent; the caller must issue a new secret with a new client_token


def test_only_one_claim_wins_and_a_live_lease_blocks_another_dispatch(db, org, as_org):
    m = accept(db, org, as_org, **reminder_request())
    with as_org(org):
        config = NotificationConfig.from_env()
        assert messages._claim(db, org.id, m.id, NOW, config) is True
        assert messages._claim(db, org.id, m.id, NOW, config) is False
        db.commit()
    t = ScriptedTransport()
    with as_org(org):
        out = messages.dispatch(db, m.id, transport=t, now=later(5))
    assert out.status == "sending" and out.attempts == 1 and not t.sent


def test_a_stale_worker_cannot_overwrite_a_newer_attempt(db, org, as_org):
    m = accept(db, org, as_org, **reminder_request())
    config = NotificationConfig.from_env()
    with as_org(org):
        assert messages._claim(db, org.id, m.id, NOW, config)  # attempt 1, then the worker stalls
        db.commit()
        assert messages._claim(db, org.id, m.id, later(500), config)  # lease expired: attempt 2 takes over
        db.commit()
        current = messages._get(db, org.id, m.id)
        assert current.attempts == 2
        messages._record(db, current, get_default(current.template_key), OK, 1, NOW, config)  # the stale result
        db.commit()
    after = fresh(db, org, as_org, m.id)
    assert after.status == "sending" and after.provider_message_id is None
    assert "notification.message.sent" not in outbox_names(db, org.id)


def test_a_message_abandoned_while_sending_is_taken_over_after_its_lease(db, org, as_org):
    m = accept(db, org, as_org, **reminder_request())
    with as_org(org):
        messages._claim(db, org.id, m.id, NOW, NotificationConfig.from_env())  # the process dies here
        db.commit()
    t = ScriptedTransport()
    assert sweep(t, later(10))["found"] == 0  # lease still live
    assert sweep(t, later(200))["redriven"] == 1
    m = fresh(db, org, as_org, m.id)
    assert m.status == "sent" and m.attempts == 2  # may be a duplicate if the first call had reached the provider


def test_an_abandoned_message_at_the_attempt_limit_is_failed_not_resent(db, org, as_org, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_MAX_ATTEMPTS", "1")
    m = accept(db, org, as_org, **reminder_request())
    with as_org(org):
        messages._claim(db, org.id, m.id, NOW, NotificationConfig.from_env())
        db.commit()
    t = ScriptedTransport()
    assert sweep(t, later(200))["failed"] == 1
    m = fresh(db, org, as_org, m.id)
    assert m.status == "failed" and m.last_error == "abandoned" and not t.sent
    assert len(outbox_events(db, org.id, "notification.message.failed")) == 1


def test_a_secret_bearing_message_abandoned_while_sending_is_outcome_unknown(db, org, as_org):
    m = accept(db, org, as_org, **verify_request())
    with as_org(org):
        messages._claim(db, org.id, m.id, NOW, NotificationConfig.from_env())
        db.commit()
    t = ScriptedTransport()
    assert sweep(t, later(200))["failed"] == 1
    m = fresh(db, org, as_org, m.id)
    assert m.status == "failed" and m.last_error == "outcome_unknown" and not t.sent


def test_a_secret_bearing_message_never_dispatched_is_failed_with_secret_unavailable(db, org, as_org):
    m = accept(db, org, as_org, **verify_request())  # committed, then the process died before dispatch
    t = ScriptedTransport()
    assert sweep(t, real_future(300))["failed"] == 1
    m = fresh(db, org, as_org, m.id)
    assert m.status == "failed" and m.last_error == "secret_unavailable" and not t.sent


def test_a_plain_message_never_dispatched_is_sent_by_recovery(db, org, as_org):
    m = accept(db, org, as_org, **reminder_request())
    t = ScriptedTransport()
    assert sweep(t, real_future(300))["redriven"] == 1
    assert fresh(db, org, as_org, m.id).status == "sent"


def test_recovery_leaves_fresh_work_alone(db, org, as_org):
    m = accept(db, org, as_org, **reminder_request())
    t = ScriptedTransport()
    result = sweep(t, datetime.now(UTC))
    assert result["found"] == 0 and not t.sent and fresh(db, org, as_org, m.id).status == "queued"


def test_recovery_handles_each_organisation_in_its_own_scope(db, org, other_org, as_org):
    a = accept(db, org, as_org, **reminder_request())
    b = accept(db, other_org, as_org, **reminder_request())
    for o, m in ((org, a), (other_org, b)):
        with as_org(o):
            messages._claim(db, o.id, m.id, NOW, NotificationConfig.from_env())  # both abandoned mid-send
            db.commit()
    t = ScriptedTransport()
    assert sweep(t, later(500))["redriven"] == 2
    assert {(m.organisation_id, m.message_id) for m in t.sent} == {(org.id, a.id), (other_org.id, b.id)}
    for o, m in ((org, a), (other_org, b)):
        (event,) = outbox_events(db, o.id, "notification.message.sent")
        assert event.payload["message_id"] == m.id and fresh(db, o, as_org, m.id).status == "sent"


def test_a_preference_changed_after_accept_still_suppresses_at_dispatch(db, org, as_org):
    m = accept(db, org, as_org, **reminder_request(user_id=org.member.id))
    with as_org(org):
        preferences.set_preferences(db, org.member.id, channels={"reminder": []})
    t = ScriptedTransport()
    with as_org(org):
        out = messages.dispatch(db, m.id, transport=t, now=NOW)
    assert out.status == "suppressed" and not t.sent


def test_dispatch_of_another_organisations_message_is_a_404(db, org, other_org, as_org):
    m = accept(db, org, as_org, **reminder_request())
    with as_org(other_org), pytest.raises(NotificationError) as e:
        messages.dispatch(db, m.id, transport=ScriptedTransport(), now=NOW)
    assert e.value.status == 404
