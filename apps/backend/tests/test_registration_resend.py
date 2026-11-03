"""Resending the verification email (#316 follow-up).

The verification email carries a token that is never stored, so notification can never re-send it: one SMTP
failure, or a closed tab, used to leave the organisation stuck in pending_verification with its slug taken.
POST /tenancy/register/resend issues a new token and mails it to the registering address, without revealing which
registrations exist and within a per-organisation limit."""

import logging
import uuid
from datetime import timedelta

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_notification.application import messages
from eos_notification.domain.errors import NotificationError
from eos_notification.infrastructure import transport as transport_module
from eos_tenancy.application import service as tenancy
from eos_tenancy.domain.models import Organisation, RegistrationToken
from sqlalchemy import select

RESEND = "/api/v1/tenancy/register/resend"
VERIFY = "/api/v1/tenancy/register/verify"


@pytest.fixture
def no_cooldown(monkeypatch):
    monkeypatch.setattr(tenancy, "RESEND_COOLDOWN", timedelta(0))


def _register(client, monkeypatch=None, *, lose_the_mail=False) -> dict:
    slug = f"resend-{uuid.uuid4().hex[:8]}"
    body = {
        "organisation_name": "Resend College",
        "slug": slug,
        "academy_type": "sports-college",
        "admin": {"name": "Admin", "email": f"admin@{slug}.example.com", "password": "Passw0rd!x"},
        "accepted_terms": True,
    }
    if lose_the_mail:

        def lost(accepted, **kwargs):
            raise RuntimeError("smtp 451 temporary failure")

        monkeypatch.setattr(messages, "deliver_accepted", lost)
    r = client.post("/api/v1/tenancy/register", json=body)
    assert r.status_code == 201, r.text
    if lose_the_mail:
        monkeypatch.setattr(messages, "deliver_accepted", _real_deliver)
    return {"slug": slug, "email": body["admin"]["email"], "first_token": r.json()["verification_token"]}


_real_deliver = messages.deliver_accepted


def _mails_to(address: str) -> list[dict]:
    return [m for m in transport_module.sent if m.get("to") == address]


def _tokens(slug: str) -> list[RegistrationToken]:
    with platform_scope(), SessionLocal() as db:
        org = db.scalar(select(Organisation).where(Organisation.slug == slug))
        return list(db.scalars(select(RegistrationToken).where(RegistrationToken.organisation_id == org.id)))


def test_a_lost_verification_mail_can_be_resent_and_only_the_new_token_verifies(
    client, monkeypatch, no_cooldown, caplog
):
    caplog.set_level(logging.INFO)
    reg = _register(client, monkeypatch, lose_the_mail=True)
    assert _mails_to(reg["email"]) == []  # the first mail never left

    r = client.post(RESEND, json={"slug": reg["slug"], "email": reg["email"].upper()})
    assert r.status_code == 202 and r.json() == {"status": "accepted"}
    (mail,) = _mails_to(reg["email"])
    new_token = mail["token"]
    assert new_token != reg["first_token"] and new_token in mail["body"]
    assert new_token not in caplog.text and reg["email"] not in caplog.text

    assert client.post(VERIFY, json={"token": reg["first_token"]}).status_code == 400  # superseded
    v = client.post(VERIFY, json={"token": new_token})
    assert v.status_code == 200 and v.json()["status"] in ("pending_approval", "active")

    # Once verified, a resend sends nothing
    assert client.post(RESEND, json={"slug": reg["slug"], "email": reg["email"]}).status_code == 202
    assert len(_mails_to(reg["email"])) == 1


def test_unknown_slug_or_wrong_address_answers_the_same_and_mails_nobody(client, no_cooldown):
    reg = _register(client)
    before = len(_tokens(reg["slug"]))
    for body in (
        {"slug": reg["slug"], "email": "attacker@example.com"},
        {"slug": f"nobody-{uuid.uuid4().hex[:6]}", "email": reg["email"]},
    ):
        r = client.post(RESEND, json=body)
        assert r.status_code == 202 and r.json() == {"status": "accepted"}
    assert _mails_to("attacker@example.com") == []
    assert len(_mails_to(reg["email"])) == 1  # only the registration's own mail
    assert len(_tokens(reg["slug"])) == before


def test_a_resend_right_after_registration_is_dropped_by_the_cooldown(client):
    reg = _register(client)
    assert client.post(RESEND, json={"slug": reg["slug"], "email": reg["email"]}).status_code == 202
    assert len(_mails_to(reg["email"])) == 1 and len(_tokens(reg["slug"])) == 1
    # The first token still works
    assert client.post(VERIFY, json={"token": reg["first_token"]}).status_code == 200


def test_at_most_five_verification_mails_a_day(client, no_cooldown):
    reg = _register(client)
    for _ in range(6):
        assert client.post(RESEND, json={"slug": reg["slug"], "email": reg["email"]}).status_code == 202
    assert len(_mails_to(reg["email"])) == tenancy.RESEND_MAX_PER_DAY
    assert len(_tokens(reg["slug"])) == tenancy.RESEND_MAX_PER_DAY


def test_without_a_mail_transport_the_resend_fails_and_the_old_token_stays_valid(client, monkeypatch, no_cooldown):
    reg = _register(client)

    def no_transport(config):
        raise NotificationError(503, "no mail transport is configured")

    monkeypatch.setattr(messages, "get_transport", no_transport)
    r = client.post(RESEND, json={"slug": reg["slug"], "email": reg["email"]})
    assert r.status_code == 503 and reg["email"] not in r.text
    monkeypatch.undo()
    assert len(_tokens(reg["slug"])) == 1
    assert client.post(VERIFY, json={"token": reg["first_token"]}).status_code == 200
