"""Registration's verification mail goes through platform/notification: recorded in the registration's transaction
(accept_in_transaction) and sent only after it commits (deliver_accepted)."""

import importlib.util
import logging
import uuid

import pytest
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from eos_notification.application import messages
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure import transport as transport_module
from eos_tenancy.application import service as tenancy
from eos_tenancy.domain.models import Organisation, RegistrationToken
from sqlalchemy import select, text

VERIFY = "tenancy.organisation.verify"


def _body(slug: str) -> dict:
    return {
        "organisation_name": slug.replace("-", " ").title(),
        "slug": slug,
        "academy_type": "sports-college",
        "admin": {"name": "Admin", "email": f"admin@{slug}.example.com", "password": "Passw0rd!x"},
        "accepted_terms": True,
    }


def _new_slug() -> str:
    return f"mail-{uuid.uuid4().hex[:8]}"


def _mails_to(address: str) -> list[dict]:
    # Every test uses its own address, so filtering is safe even though the list is trimmed when it grows.
    return [m for m in transport_module.sent if m.get("to") == address]


def _messages_to(address: str) -> list[Message]:
    with platform_scope(), SessionLocal() as db:
        return list(db.scalars(select(Message).where(Message.recipient_address == address)))


def _stored(slug: str):
    """The organisation, its registration token row and its notification messages, or (None, None, [])."""
    with platform_scope(), SessionLocal() as db:
        org = db.scalar(select(Organisation).where(Organisation.slug == slug))
        if org is None:
            return None, None, []
        issued = db.scalar(select(RegistrationToken).where(RegistrationToken.organisation_id == org.id))
        rows = list(db.scalars(select(Message).where(Message.organisation_id == org.id)))
        return org, issued, rows


def test_registration_sends_the_verification_mail_through_notification(client):
    slug = _new_slug()
    body = _body(slug)
    address = body["admin"]["email"]
    r = client.post("/api/v1/tenancy/register", json=body)
    assert r.status_code == 201, r.text
    token = r.json()["verification_token"]  # dev mode, as before
    (mail,) = _mails_to(address)
    assert mail["subject"] == "Verify your Education OS organisation"
    assert mail["token"] == token and token in mail["body"] and body["organisation_name"] in mail["body"]
    _, issued, (message,) = _stored(slug)
    assert message.template_key == VERIFY and message.client_token == f"tenancy:verify:{issued.id}"
    assert message.status == "sent" and mail["message_id"] == message.id
    assert client.post("/api/v1/tenancy/register/verify", json={"token": token}).status_code == 200


@pytest.mark.skipif(importlib.util.find_spec("eos_core.notify") is None, reason="the legacy stub is deleted")
def test_registration_no_longer_uses_the_legacy_stub(client):
    from eos_core import notify

    body = _body(_new_slug())
    assert client.post("/api/v1/tenancy/register", json=body).status_code == 201
    assert not [m for m in notify.sent if m.get("to") == body["admin"]["email"]]


def test_the_token_is_not_stored_logged_or_published_by_the_mail(client, caplog):
    """The mail's side only: tenancy_registration_token keeps the token, as it did before, to look it up."""
    caplog.set_level(logging.DEBUG)
    slug = _new_slug()
    r = client.post("/api/v1/tenancy/register", json=_body(slug))
    token = r.json()["verification_token"]
    org, _, _ = _stored(slug)
    with platform_scope(), SessionLocal() as db:
        rows = db.execute(text("SELECT * FROM notification_message WHERE organisation_id = :o"), {"o": org.id}).all()
        payloads = [
            str(e.payload) for e in db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org.id))
        ]
    assert rows and not any(token in str(value) for row in rows for value in row)
    assert payloads and not any(token in p for p in payloads)
    assert token not in caplog.text


def test_nothing_is_sent_or_kept_when_the_registration_does_not_commit(client, monkeypatch):
    slug = _new_slug()
    body = _body(slug)
    db = SessionLocal()

    def commit_fails():
        raise RuntimeError("commit failed")

    monkeypatch.setattr(db, "commit", commit_fails)
    try:
        with pytest.raises(RuntimeError):
            tenancy.register(
                db,
                organisation_name=body["organisation_name"],
                slug=slug,
                academy_type=body["academy_type"],
                admin=body["admin"],
                accepted_terms=True,
            )
        db.rollback()
    finally:
        db.close()
    assert _mails_to(body["admin"]["email"]) == []
    assert _stored(slug)[0] is None and _messages_to(body["admin"]["email"]) == []


def test_a_refused_mail_refuses_the_registration_and_keeps_nothing(client, monkeypatch):
    def no_transport(config):
        raise NotificationError(503, "no mail transport is configured")

    monkeypatch.setattr(messages, "get_transport", no_transport)
    slug = _new_slug()
    body = _body(slug)
    address = body["admin"]["email"]
    r = client.post("/api/v1/tenancy/register", json=body)
    assert r.status_code == 503 and "verification email cannot be sent" in r.text and address not in r.text
    assert _stored(slug)[0] is None and _messages_to(address) == [] and _mails_to(address) == []
    monkeypatch.undo()
    assert client.post("/api/v1/tenancy/register", json=body).status_code == 201  # the slug was never taken


def test_a_refused_mail_leaves_nothing_for_a_caller_that_commits_afterwards(client, monkeypatch):
    """register() rolls back itself. Over HTTP the closed session would hide a missing rollback; an in-process
    caller that catches the error and commits must still not keep half a registration."""

    def no_transport(config):
        raise NotificationError(503, "no mail transport is configured")

    monkeypatch.setattr(messages, "get_transport", no_transport)
    slug = _new_slug()
    body = _body(slug)
    with SessionLocal() as db:
        with pytest.raises(tenancy.TenancyError) as e:
            tenancy.register(
                db,
                organisation_name=body["organisation_name"],
                slug=slug,
                academy_type=body["academy_type"],
                admin=body["admin"],
                accepted_terms=True,
            )
        db.commit()
    assert e.value.status == 503
    assert _stored(slug)[0] is None and _messages_to(body["admin"]["email"]) == []


def test_a_delivery_failure_after_the_commit_keeps_the_registration(client, monkeypatch, caplog):
    def broken(accepted, **kwargs):
        raise RuntimeError("provider unreachable")

    monkeypatch.setattr(messages, "deliver_accepted", broken)
    caplog.set_level(logging.WARNING, logger="eos.tenancy")
    slug = _new_slug()
    body = _body(slug)
    r = client.post("/api/v1/tenancy/register", json=body)
    assert r.status_code == 201, r.text
    token = r.json()["verification_token"]
    _, _, (message,) = _stored(slug)
    assert message.status == "queued"  # accepted, not delivered, and not reported as delivered
    assert f"verification mail {message.id} not delivered: RuntimeError" in caplog.text
    assert token not in caplog.text and body["admin"]["email"] not in caplog.text


def test_a_repeated_registration_sends_one_mail(client):
    slug = _new_slug()
    body = _body(slug)
    assert client.post("/api/v1/tenancy/register", json=body).status_code == 201
    assert client.post("/api/v1/tenancy/register", json=body).status_code == 409
    assert len(_mails_to(body["admin"]["email"])) == 1 and len(_stored(slug)[2]) == 1


def test_if_the_process_stops_before_delivery_the_mail_is_lost_not_misreported(client, monkeypatch):
    """The gap this patch does not close: durable dispatch is the outbox relay's job (#83). The token lived only
    in memory, so a later attempt cannot send the mail; it is marked failed, never sent with a missing token."""
    monkeypatch.setattr(tenancy, "_deliver_verification", lambda accepted: None)  # the process stops here
    slug = _new_slug()
    body = _body(slug)
    assert client.post("/api/v1/tenancy/register", json=body).status_code == 201
    org, _, (message,) = _stored(slug)
    assert message.status == "queued" and _mails_to(body["admin"]["email"]) == []
    with organisation_scope(org.id), SessionLocal() as db:
        later = messages.dispatch(db, message.id)
    assert later.status == "failed" and later.last_error == "secret_unavailable"
    assert _mails_to(body["admin"]["email"]) == []
