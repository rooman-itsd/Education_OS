import dataclasses
import logging
import uuid

import pytest
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_notification.application import messages, preferences
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure import transport as transport_module
from notification_support import NOW, ScriptedTransport, later, outbox_names, reminder_request, verify_request
from sqlalchemy import select, text

SECRET = "s3cr3t-token-value"


def send(db, org, as_org, **request):
    with as_org(org):
        return messages.send_message(db, now=NOW, **request)


def test_verification_mail_is_sent_through_the_memory_transport(db, org, as_org):
    message, created = send(db, org, as_org, **verify_request())
    assert created and message.status == "sent"
    assert message.provider_message_id == f"memory:{message.id}" and message.attempts == 1
    (mail,) = transport_module.sent  # the record shape the legacy eos_core.notify stub used
    assert mail["to"] == "admin@college.example.com" and mail["token"] == SECRET and SECRET in mail["body"]
    assert outbox_names(db, org.id) == ["notification.message.sent"]


def test_a_secret_is_never_stored_or_logged_or_published(db, org, as_org, caplog):
    caplog.set_level(logging.DEBUG)
    message, _ = send(db, org, as_org, **verify_request())
    assert message.body is None and "token" not in message.variables and SECRET not in str(message.variables)
    rows = db.execute(text("SELECT * FROM notification_message")).all()
    assert rows and not any(SECRET in str(value) for row in rows for value in row)
    with platform_scope():
        payloads = [str(e.payload) for e in db.scalars(select(OutboxEvent))]
    assert not any(SECRET in p for p in payloads)
    assert SECRET not in caplog.text and "admin@college.example.com" not in caplog.text


def test_verify_needs_a_client_token_and_an_issuance_id(db, org, as_org):
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **verify_request(client_token=None))
    assert e.value.status == 422
    request = verify_request()
    del request["variables"]["token_id"]
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **request)
    assert e.value.status == 422 and "token_id" in e.value.detail and SECRET not in e.value.detail


def test_retry_with_the_same_token_and_issuance_returns_the_original_and_sends_once(db, org, as_org):
    request = verify_request()
    first, created1 = send(db, org, as_org, **request)
    second, created2 = send(db, org, as_org, **request)
    assert created1 and not created2 and first.id == second.id and len(transport_module.sent) == 1


def test_reusing_a_client_token_for_a_new_issuance_is_refused_not_silently_dropped(db, org, as_org):
    request = verify_request()
    send(db, org, as_org, **request)
    changed = verify_request(client_token=request["client_token"])  # new token_id, new secret, same client_token
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **changed)
    assert e.value.status == 422 and len(transport_module.sent) == 1


def test_a_new_issuance_with_a_new_client_token_is_sent(db, org, as_org):
    send(db, org, as_org, **verify_request())
    send(db, org, as_org, **verify_request())
    assert len(transport_module.sent) == 2


def test_documented_limit_same_issuance_id_with_a_different_secret_cannot_be_detected(db, org, as_org):
    """secret_ref is the caller's promise that one id names one secret; the service never sees or stores secrets,
    so it cannot check that promise. It replays the original and does NOT send the second secret."""
    request = verify_request()
    send(db, org, as_org, **request)
    other = {**request, "variables": {**request["variables"], "token": "a-different-secret"}}
    _, created = send(db, org, as_org, **other)
    assert not created and len(transport_module.sent) == 1


def test_client_token_idempotency_is_per_organisation(db, org, other_org, as_org):
    request = reminder_request(client_token="same-token")
    a, _ = send(db, org, as_org, **request)
    b, created = send(db, other_org, as_org, **request)
    assert created and a.id != b.id and a.organisation_id == org.id and b.organisation_id == other_org.id


def test_event_redelivery_makes_one_message_even_with_a_differently_written_id(db, org, as_org):
    event = str(uuid.uuid4())
    kwargs = dict(
        template="billing.trial.expired",
        recipient={"address": "p@college.example.com"},
        variables={"organisation_name": "C"},
        channel="email",
    )
    with as_org(org):
        first = messages.accept_message(db, source_event_id=event, **kwargs)
        db.commit()
        second = messages.accept_message(db, source_event_id=event.upper(), **kwargs)  # redelivered, other spelling
        db.commit()
    assert first.created and not second.created and first.message.id == second.message.id
    with as_org(org):
        rows = db.scalars(select(Message).where(Message.source_event_id == event)).all()
    assert len(rows) == 1


def test_one_event_can_notify_two_recipients(db, org, as_org):
    event = str(uuid.uuid4())
    with as_org(org):
        for who in ("a@college.example.com", "b@college.example.com"):
            messages.accept_message(
                db, template="billing.trial.expired", recipient={"address": who},
                variables={"organisation_name": "C"}, source_event_id=event, channel="email",
            )  # fmt: skip
            db.commit()
        rows = db.scalars(select(Message).where(Message.source_event_id == event)).all()
    assert len(rows) == 2


def test_a_malformed_event_id_is_refused(db, org, as_org):
    with as_org(org), pytest.raises(NotificationError):
        messages.accept_message(
            db, template="billing.trial.expired", recipient={"address": "p@college.example.com"},
            variables={"organisation_name": "C"}, source_event_id="not-a-uuid",
        )  # fmt: skip


@pytest.mark.parametrize(
    "mutate",
    [
        lambda r: r.update(template="made.up"),
        lambda r: r["variables"].pop("trial_ends_on"),
        lambda r: r.update(attachments=[{"document_id": str(uuid.uuid4())}]),
        lambda r: r.update(send_after=later(3600)),
        lambda r: r.update(category="transactional"),  # does not match the template's category
        lambda r: r.update(channel="sms"),
        lambda r: r.update(recipient={"user_id": str(uuid.uuid4())}),  # no such user
        lambda r: r.update(recipient={"address": "not-an-address"}),
        lambda r: r.update(recipient={"address": "p@college.example.com"}, channel="in_app"),
    ],
)
def test_invalid_requests_are_a_422_and_queue_nothing(db, org, as_org, mutate):
    request = reminder_request()
    mutate(request)
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **request)
    assert e.value.status == 422 and not transport_module.sent
    with as_org(org):
        assert db.scalars(select(Message).where(Message.organisation_id == org.id)).first() is None


def test_a_missing_variable_names_the_variable_not_its_neighbours_values(db, org, as_org):
    request = reminder_request()
    request["variables"] = {"organisation_name": "PRIVATE-NAME"}
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **request)
    assert "trial_ends_on" in e.value.detail and "PRIVATE-NAME" not in e.value.detail


def test_a_user_in_another_organisation_looks_like_no_address(db, org, other_org, as_org):
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **reminder_request(user_id=other_org.member.id))
    assert e.value.status == 422 and e.value.detail == "no address for the channel"


def test_a_user_recipient_gets_the_identity_address_not_a_caller_supplied_one(db, org, as_org):
    request = reminder_request(user_id=org.member.id)
    request["recipient"]["address"] = "attacker@evil.example"
    message, _ = send(db, org, as_org, **request)
    assert message.recipient_address == org.member.email and transport_module.sent[-1]["to"] == org.member.email


def test_preferences_suppress_non_transactional_mail_and_send_nothing(db, org, as_org):
    with as_org(org):
        preferences.set_preferences(db, org.member.id, channels={"reminder": []})
    message, _ = send(db, org, as_org, **reminder_request(user_id=org.member.id))
    assert message.status == "suppressed" and not transport_module.sent
    assert "notification.message.sent" not in outbox_names(db, org.id)


def test_transactional_mail_ignores_preferences(db, org, as_org):
    with as_org(org):
        preferences.set_preferences(
            db, org.member.id, channels={c: [] for c in ("operational", "reminder", "announcement", "transactional")}
        )
    request = verify_request(recipient={"user_id": org.member.id})
    message, _ = send(db, org, as_org, **request)
    assert message.status == "sent" and len(transport_module.sent) == 1


def test_in_app_message_is_delivered_without_a_provider_and_keeps_its_body(db, org, as_org):
    message, _ = send(db, org, as_org, **reminder_request(user_id=org.member.id, channel="in_app"))
    assert message.status == "delivered" and message.sent_at and message.body and not transport_module.sent


def test_memory_transport_is_refused_outside_dev_mode_and_nothing_is_queued(db, org, as_org, monkeypatch):
    monkeypatch.setattr(transport_module, "settings", dataclasses.replace(transport_module.settings, dev_mode=False))
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **reminder_request())
    assert e.value.status == 503
    with as_org(org):
        assert db.scalars(select(Message).where(Message.organisation_id == org.id)).first() is None


@pytest.mark.parametrize(
    "env",
    [
        {"NOTIFICATION_TRANSPORT": "carrier-pigeon"},  # unknown transport
        # `adapter` is a real transport now, so unavailability has to be real too: configured, but naming an
        # adapter that is not installed. Still a 503 before anything is written, still no fallback to memory.
        {"NOTIFICATION_TRANSPORT": "adapter", "NOTIFICATION_ADAPTER": "not-installed"},
        {"NOTIFICATION_TRANSPORT": "adapter", "NOTIFICATION_ADAPTER": ""},
    ],
)
def test_other_transports_fail_closed_instead_of_falling_back_to_memory(db, org, as_org, monkeypatch, env):
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    with pytest.raises(NotificationError) as e:
        send(db, org, as_org, **reminder_request())
    assert e.value.status == 503 and not transport_module.sent


def test_no_organisation_context_fails_closed(db):
    with pytest.raises(NotificationError) as e:
        messages.send_message(db, **reminder_request())
    assert e.value.status == 403


def test_get_message_is_scoped_to_the_organisation(db, org, other_org, as_org):
    message, _ = send(db, org, as_org, **reminder_request())
    with as_org(other_org), pytest.raises(NotificationError) as e:
        messages.get_message(db, message.id)
    assert e.value.status == 404  # not 403: another organisation's id is not confirmed to exist
    with as_org(org):
        assert messages.get_message(db, message.id).id == message.id


def test_scripted_transport_is_used_when_given(db, org, as_org):
    t = ScriptedTransport()
    with as_org(org):
        messages.send_message(db, transport=t, now=NOW, **reminder_request())
    assert len(t.sent) == 1 and not transport_module.sent


# --- one idempotency contract: client_token is the only key (docs/idempotency.md) ---------------------------

EVENT_SEND = dict(
    template="billing.trial.expired",
    recipient={"address": "P@College.Example.com"},  # upper case on purpose: the key is the lower-cased address
    variables={"organisation_name": "C"},
    channel="email",
)


def test_an_event_linked_send_derives_its_client_token_from_the_canonical_event(db, org, as_org):
    event = str(uuid.uuid4())
    with as_org(org):
        accepted = messages.accept_message(db, source_event_id=event.upper(), **EVENT_SEND)
        db.commit()
    expected = messages.event_token(event, "billing.trial.expired", "email", "p@college.example.com")
    assert accepted.message.client_token == expected
    assert expected.startswith("evt:") and len(expected) == 68  # inside the 120-character column


def test_a_client_token_that_disagrees_with_the_derived_one_is_refused(db, org, as_org):
    with as_org(org), pytest.raises(NotificationError) as e:
        messages.accept_message(db, source_event_id=str(uuid.uuid4()), client_token="mine", **EVENT_SEND)
    assert e.value.status == 422


def test_the_derived_token_may_be_supplied_explicitly(db, org, as_org):
    """A relay that computes the same token itself is agreeing with the service, not fighting it."""
    event = str(uuid.uuid4())
    token = messages.event_token(event, "billing.trial.expired", "email", "p@college.example.com")
    with as_org(org):
        accepted = messages.accept_message(db, source_event_id=event, client_token=token, **EVENT_SEND)
        db.commit()
    assert accepted.created and accepted.message.client_token == token


def test_an_event_redelivery_whose_variables_changed_is_refused(db, org, as_org):
    """The decision in docs/idempotency.md: the same event, template, channel and recipient with different
    content means a broken relay or producer, so it is a 422 rather than a silent return of the original.
    To keep the old behaviour instead, stop computing a fingerprint for a derived token."""
    event = str(uuid.uuid4())
    with as_org(org):
        messages.accept_message(db, source_event_id=event, **EVENT_SEND)
        db.commit()
        with pytest.raises(NotificationError) as e:
            messages.accept_message(
                db, source_event_id=event, **{**EVENT_SEND, "variables": {"organisation_name": "DIFFERENT"}}
            )
    assert e.value.status == 422


def test_the_derived_token_keys_off_the_recipient_as_asked_not_as_resolved(db, org, as_org):
    """A redelivery must be recognised from the request alone, so the token may never depend on a lookup whose
    answer can change (identity, preferences, account status) between one delivery and the next."""
    event = str(uuid.uuid4())
    with as_org(org):
        accepted = messages.accept_message(
            db, source_event_id=event, **{**EVENT_SEND, "recipient": {"user_id": org.member.id}}
        )
        db.commit()
    assert accepted.message.client_token == messages.event_token(event, "billing.trial.expired", "email", org.member.id)
