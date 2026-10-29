"""Regression tests for the review findings. Each one failed before its fix."""

import dataclasses
from datetime import UTC, datetime, timedelta

import pytest
from eos_notification.application import messages, preferences, templates
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure import transport as transport_module
from notification_support import NOW, ScriptedTransport, reminder_request, verify_request

SECRET = "s3cr3t-token-value"


def send(db, org, as_org, **request):
    with as_org(org):
        return messages.send_message(db, now=NOW, **request)


# --- 1. a genuine retry returns the original, whatever changed since ------------------------------------------


def test_retry_returns_the_original_after_the_user_changed_preferences(db, org, as_org):
    request = reminder_request(user_id=org.member.id)
    first, _ = send(db, org, as_org, **request)
    with as_org(org):
        preferences.set_preferences(db, org.member.id, channels={"reminder": ["in_app"]})
    again, created = send(db, org, as_org, **request)
    assert not created and again.id == first.id and again.channel == "email" and len(transport_module.sent) == 1


def test_retry_returns_the_original_after_the_user_was_deactivated(db, org, as_org):
    request = reminder_request(user_id=org.member.id)
    first, _ = send(db, org, as_org, **request)
    org.member.status = "disabled"
    db.add(org.member)
    db.commit()
    again, created = send(db, org, as_org, **request)
    assert not created and again.id == first.id and len(transport_module.sent) == 1


@pytest.mark.parametrize(
    "change",
    [
        lambda r: r["variables"].update(days_left=9),
        lambda r: r.update(recipient={"address": "someone-else@college.example.com"}),
        lambda r: r.update(template="billing.trial.expired", variables={"organisation_name": "C"}),
        lambda r: r.update(channel="in_app"),
    ],
)
def test_the_same_token_for_a_genuinely_different_request_is_still_refused(db, org, as_org, change):
    request = reminder_request()
    send(db, org, as_org, **request)
    other = {**request, "variables": dict(request["variables"]), "recipient": dict(request["recipient"])}
    change(other)
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **other)
    assert e.value.status == 422 and len(transport_module.sent) == 1


# --- 2. one bad message cannot stop the recovery sweep -------------------------------------------------------


def _stuck(db, org, as_org, key="billing.trial.expired", minutes=60) -> Message:
    with as_org(org):
        m = Message(
            organisation_id=org.id,
            template_key=key,
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


def test_a_retired_template_is_failed_safely_and_the_sweep_continues(db, org, as_org):
    bad = _stuck(db, org, as_org, key="retired.template", minutes=90)
    good = _stuck(db, org, as_org, minutes=60)
    t = ScriptedTransport()
    counts = messages.recover_stuck(transport=t, now=datetime.now(UTC))
    assert counts["failed"] == 1 and counts["redriven"] == 1
    with as_org(org):
        assert messages.get_message(db, bad.id).last_error == "template_unavailable"
        assert messages.get_message(db, good.id).status == "sent"


def test_an_unexpected_error_on_one_message_does_not_stop_the_others(db, org, as_org, monkeypatch):
    first = _stuck(db, org, as_org, minutes=90)
    second = _stuck(db, org, as_org, minutes=60)
    real = messages.dispatch

    def flaky(db, message_id, **kw):
        if message_id == first.id:
            raise RuntimeError("bug with p@college.example.com in it")
        return real(db, message_id, **kw)

    monkeypatch.setattr(messages, "dispatch", flaky)
    counts = messages.recover_stuck(transport=ScriptedTransport(), now=datetime.now(UTC))
    assert counts["errors"] == 1 and counts["redriven"] == 1
    with as_org(org):
        assert messages.get_message(db, first.id).status == "queued"  # left for the next sweep
        assert messages.get_message(db, second.id).status == "sent"


def test_a_provider_failure_on_one_message_does_not_stop_the_others(db, org, as_org):
    first = _stuck(db, org, as_org, minutes=90)
    second = _stuck(db, org, as_org, minutes=60)
    t = ScriptedTransport(RuntimeError("provider down"), transport_module.SendResult(True, "p-2"))
    messages.recover_stuck(transport=t, now=datetime.now(UTC))
    with as_org(org):
        assert messages.get_message(db, first.id).last_error == "transport_error"
        assert messages.get_message(db, second.id).status == "sent"


def test_no_transport_available_leaves_messages_untouched_without_raising(db, org, as_org, monkeypatch):
    m = _stuck(db, org, as_org)
    # A genuinely unavailable transport: the adapter transport exists, but this names one that is not installed.
    monkeypatch.setenv("NOTIFICATION_TRANSPORT", "adapter")
    monkeypatch.setenv("NOTIFICATION_ADAPTER", "not-installed")
    counts = messages.recover_stuck(now=datetime.now(UTC))
    assert counts["skipped"] == 1
    with as_org(org):
        stored = messages.get_message(db, m.id)
    assert stored.status == "queued" and stored.attempts == 0


# --- 3. secrets never reach provider metadata ------------------------------------------------------------------


def test_provider_metadata_never_carries_a_secret_and_repr_hides_the_body(db, org, as_org):
    t = ScriptedTransport()
    with as_org(org):
        messages.send_message(db, transport=t, now=NOW, **verify_request())
    (outbound,) = t.sent
    assert SECRET not in str(outbound.metadata)  # metadata is echoed back on provider receipts
    assert SECRET in outbound.body  # the mail itself must still carry the token
    assert SECRET not in repr(outbound)  # a stray log line of the message cannot leak it


def test_the_dev_transport_still_exposes_the_token_for_eos_testing(db, org, as_org):
    send(db, org, as_org, **verify_request())
    assert transport_module.sent[-1]["token"] == SECRET


# --- 6. in-app needs no transport; wording is fixed at acceptance ---------------------------------------------


def test_in_app_messages_do_not_need_a_transport(db, org, as_org, monkeypatch):
    monkeypatch.setattr(transport_module, "settings", dataclasses.replace(transport_module.settings, dev_mode=False))
    message, _ = send(db, org, as_org, **reminder_request(user_id=org.member.id, channel="in_app"))
    assert message.status == "delivered"


def test_a_message_is_sent_with_the_wording_it_was_accepted_with(db, org, as_org):
    with as_org(org):
        accepted = messages.accept_message(db, now=NOW, **reminder_request())
        db.commit()
        templates.upsert_template(
            db, key="billing.trial.reminder", channel="email", locale="en", subject="EDITED", body="EDITED ${days_left}"
        )
        messages.dispatch(db, accepted.message.id, transport=None, now=NOW)
    mail = transport_module.sent[-1]
    assert mail["subject"].startswith("Your trial ends") and "EDITED" not in mail["body"]


def test_a_redelivered_event_is_deduplicated_even_after_the_user_was_deactivated(db, org, as_org):
    import uuid

    event = str(uuid.uuid4())
    request = dict(
        template="billing.trial.expired",
        recipient={"user_id": org.member.id},
        variables={"organisation_name": "C"},
        source_event_id=event,
        channel="email",
    )
    with as_org(org):
        first = messages.accept_message(db, now=NOW, **request)
        db.commit()
        org.member.status = "disabled"  # a write to an identity row: needs this organisation's scope on PG
        db.add(org.member)
        db.commit()
    with as_org(org):
        again = messages.accept_message(db, now=NOW, **request)
    assert not again.created and again.message.id == first.message.id
