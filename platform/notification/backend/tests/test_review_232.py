"""Regressions from the PR #232 review: values the database or a provider could hand back that the code took on
trust (rendered subject length, provider id length, retry hints), a CRLF in a subject override, and the own-
preferences check on a non-canonical id."""

import pytest
from eos_core import config as core_config
from eos_notification.api.router import router
from eos_notification.application import messages, templates
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure.config import NotificationConfig
from eos_notification.infrastructure.templates import render
from eos_notification.infrastructure.transport import AdapterTransport, SendResult
from fastapi import FastAPI
from fastapi.testclient import TestClient
from notification_support import NOW, PREFIX, ScriptedTransport, later, reminder_request
from sqlalchemy import func, select
from sqlalchemy.exc import DataError


@pytest.fixture(autouse=True)
def grants(monkeypatch):
    real = core_config.load_role_grants()
    monkeypatch.setattr(core_config, "load_role_grants", lambda: {**real, "test-sender": {"notification:message:send"}})


class _Provider:
    def __init__(self, **result):
        self.result = type("R", (), result)()

    def send(self, **kwargs):
        return self.result


def _count(db) -> int:
    return db.scalar(select(func.count()).select_from(Message)) or 0


# F1 -----------------------------------------------------------------------------------------------------------


def test_a_rendered_subject_longer_than_its_column_is_a_422_and_queues_nothing(db, org, as_org):
    request = reminder_request(
        template="billing.invoice.issued",
        variables={"organisation_name": "x" * 2000, "invoice_number": "1", "amount": "1", "due_on": "d"},
    )
    with as_org(org), pytest.raises(NotificationError) as e:
        messages.send_message(db, transport=ScriptedTransport(), **request)
    assert e.value.status == 422 and "x" not in e.value.detail
    db.rollback()
    assert _count(db) == 0
    # the same bound applies to an organisation's own wording
    with as_org(org):
        templates.upsert_template(
            db,
            key="billing.trial.reminder",
            channel="email",
            locale="en",
            subject="y" * 280 + " ${days_left}",
            body="b",
        )
        with pytest.raises(NotificationError) as e:
            messages.send_message(
                db,
                transport=ScriptedTransport(),
                **reminder_request(variables={"organisation_name": "C", "trial_ends_on": "d", "days_left": "x" * 20}),
            )
    assert e.value.status == 422
    db.rollback()
    assert _count(db) == 0


def test_a_data_error_on_insert_is_a_500_that_exposes_no_row_values(db, org, as_org, monkeypatch, caplog):
    address = "leak-me@college.example.com"

    def refuse(*_a, **_k):
        raise DataError("INSERT ...", {"recipient_address": address}, Exception("value too long"))

    monkeypatch.setattr(db, "flush", refuse)
    with as_org(org), pytest.raises(NotificationError) as e:
        messages.accept_message(db, **reminder_request(recipient={"address": address}))
    assert e.value.status == 500 and address not in e.value.detail
    assert address not in str(e.value.__cause__) and address not in caplog.text


# F2 -----------------------------------------------------------------------------------------------------------


def test_a_provider_message_id_is_cut_to_the_column_and_a_non_string_is_dropped():
    long_id = AdapterTransport(lambda ch: _Provider(accepted=True, provider_message_id="p" * 500)).send(_outbound())
    assert long_id.accepted and len(long_id.provider_message_id) == 200
    odd = AdapterTransport(lambda ch: _Provider(accepted=True, provider_message_id=12345)).send(_outbound())
    assert odd.accepted and odd.provider_message_id is None


# F3 -----------------------------------------------------------------------------------------------------------


def test_a_retry_hint_is_a_positive_integer_clamped_to_the_cap_or_ignored(db, org, as_org):
    factory = lambda ch: _Provider(accepted=False, reason="throttled", retryable=True, retry_after_s=10**12)  # noqa: E731
    assert AdapterTransport(factory, max_retry_delay_s=3600).send(_outbound()).retry_after_s == 3600
    for bad in (-5, 0, "60", True, None, 1.5):
        f = lambda ch, bad=bad: _Provider(accepted=False, reason="throttled", retryable=True, retry_after_s=bad)  # noqa: E731
        assert AdapterTransport(f, max_retry_delay_s=3600).send(_outbound()).retry_after_s is None
    # and the service clamps once more, so a transport given directly cannot overflow the timestamp either
    config = NotificationConfig.from_env()
    with as_org(org):
        huge = ScriptedTransport(SendResult(False, reason="throttled", retryable=True, retry_after_s=10**12))
        msg, _ = messages.send_message(db, transport=huge, now=NOW, config=config, **reminder_request())
        assert msg.status == "queued" and messages.aware(msg.next_attempt_at) == later(config.recovery_max_delay_s)
        past = ScriptedTransport(SendResult(False, reason="throttled", retryable=True, retry_after_s=-999999))
        msg, _ = messages.send_message(db, transport=past, now=NOW, config=config, **reminder_request())
        assert messages.aware(msg.next_attempt_at) == later(config.retry_backoff_s)  # the backoff, not the past


# F4 -----------------------------------------------------------------------------------------------------------


def test_a_subject_override_with_a_line_break_is_refused_and_render_never_emits_one(db, org, as_org):
    with as_org(org):
        for subject in ("Trial\r\nBcc: attacker@evil.example", "Trial\nBcc: x", "Trial\rBcc: x"):
            with pytest.raises(NotificationError) as e:
                templates.upsert_template(
                    db, key="billing.trial.reminder", channel="email", locale="en", subject=subject, body="b"
                )
            assert e.value.status == 422
    assert render("a\r\nb ${n}", {"n": "c\nd"}, single_line=True) == "a b c d"
    assert render("a\r\nb", {}) == "a\r\nb"  # bodies keep their lines


# F6 -----------------------------------------------------------------------------------------------------------


def test_own_preferences_are_reachable_with_any_spelling_of_own_id(org):
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    client = TestClient(app)
    me, other = org.member, org.admin
    for spelling in (me.id, me.id.upper(), "{" + me.id + "}"):
        r = client.get(f"{PREFIX}/preferences/{spelling}", headers=org.headers(me))
        assert r.status_code == 200 and r.json()["user_id"] == me.id, spelling
        r = client.put(f"{PREFIX}/preferences/{spelling}", json={"channels": {"reminder": []}}, headers=org.headers(me))
        assert r.status_code == 200 and r.json()["channels"]["reminder"] == [], spelling
    assert client.get(f"{PREFIX}/preferences/{other.id.upper()}", headers=org.headers(me)).status_code == 403
    assert client.get(f"{PREFIX}/preferences/not-an-id", headers=org.headers(me)).status_code == 422


def _outbound():
    from eos_notification.infrastructure.transport import OutboundMessage

    return OutboundMessage(
        message_id="m", organisation_id="o", channel="email", to="a@b.c", sender="s", subject="s", body="b"
    )
