"""What notification sends when the relay hands it another module's event: the right template to the
organisation's admins, once per event however often it is redelivered, and nothing at all when it cannot say
which organisation the mail is about."""

from __future__ import annotations

import logging
import uuid
from types import SimpleNamespace

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import organisation_scope
from eos_identity.domain.models import User
from eos_notification.application import consumers, organisations
from eos_notification.domain.models import Message
from eos_notification.infrastructure import transport as transport_module
from notification_support import Org
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


def test_nothing_is_sent_when_the_organisation_name_cannot_be_resolved(monkeypatch, caplog):
    """An unwired entry point must not produce "The trial for  has ended"."""
    monkeypatch.setattr(organisations.hooks, "name", lambda db, organisation_id: None)
    o = Org.create(SessionLocal())
    with caplog.at_level(logging.ERROR, logger="eos.notification"):
        deliver(event("billing.trial.expired", o.id))
    assert messages_of(o.id) == [] and transport_module.sent == []
    assert "no organisation name" in caplog.text


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
