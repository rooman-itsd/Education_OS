"""The #79 activation follow-up: the permission scheme the host's route-coverage check needs, the in-process
send path for a caller that owns its transaction, the memory transport's own record, and the host catalogue."""

from __future__ import annotations

import ast
import importlib
import importlib.util
import inspect
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import yaml
from eos_core import config as core_config
from eos_core import events
from eos_core.config import permissions_for
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from eos_identity.application.service import create_user
from eos_notification.api.router import router
from eos_notification.application import messages
from eos_notification.domain.errors import NotificationError
from eos_notification.domain.models import Message
from eos_notification.infrastructure import transport as transport_module
from eos_notification.infrastructure.transport import MemoryTransport, OutboundMessage, SendResult
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from notification_support import PREFIX, ScriptedTransport, auth, outbox_names, reminder_request, verify_request
from sqlalchemy import select

MODULE = Path(__file__).resolve().parents[2]
REPO = Path(__file__).resolve().parents[4]
SELF_KEYS = {"notification:self:read", "notification:self:manage"}
ADMIN_KEYS = {
    "notification:message:read",
    "notification:message:resend",
    "notification:template:read",
    "notification:template:write",
    "notification:preference:manage",
}


def _catalogue() -> dict:
    return yaml.safe_load((MODULE / "contracts/permissions.yaml").read_text())


def _notification_keys(roles: list[str], super_admin: bool = False) -> set[str]:
    """permissions_for unions every catalogue in the repo, so keep only this module's keys."""
    return {k for k in permissions_for(roles, super_admin) if k.startswith(("notification:", "platform:notification"))}


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    return TestClient(app)


# --- permissions ---------------------------------------------------------------------------------------


def test_every_route_names_a_key_from_this_catalogue_that_some_block_grants():
    """What the host's route-coverage check asks of every mounted platform route, checked here with the module
    alone. Before this change four routes named no key and message:send had no holder."""
    catalogue = _catalogue()
    keys = {p["key"] for p in catalogue["permissions"]}
    granted = {k for block in catalogue["roles"] for k in block["grants"]}
    for route in router.routes:
        assert isinstance(route, APIRoute)
        named = [getattr(d.call, "permission", None) for d in route.dependant.dependencies]
        named = [k for k in named if k]
        assert len(named) == 1, f"{route.path} names {named}"
        assert named[0] in keys and named[0] in granted, f"{route.path} -> {named[0]}"


def test_blocks_are_named_with_platform_role_ids():
    """permissions_for looks grants up by block name and tokens carry profile role ids, so a block named after
    this module (the old notification-admin and notification-viewer) granted nothing to anyone."""
    assert {block["name"] for block in _catalogue()["roles"]} == {"member", "org-admin", "super-admin", "service"}


def test_message_send_is_held_only_by_the_service_block():
    holders = [b["name"] for b in _catalogue()["roles"] if "notification:message:send" in b["grants"]]
    assert holders == ["service"]


def test_each_role_receives_exactly_its_share_of_the_scheme():
    assert _notification_keys(["member"]) == SELF_KEYS
    assert _notification_keys(["org-admin"]) == ADMIN_KEYS
    assert _notification_keys(["service"]) == {"notification:message:send"}
    assert "platform:notification:read" in _notification_keys([], super_admin=True)
    assert "notification:message:send" not in _notification_keys(["org-admin", "member"])


def test_the_own_resource_routes_are_guarded_by_the_self_keys(client, org, monkeypatch):
    """Take the self keys away from `member` and the four routes refuse even the owner: the guard is the key,
    not just "belongs to an organisation"."""
    real = core_config.load_role_grants()
    stripped = {name: set(keys) - SELF_KEYS for name, keys in real.items()}
    monkeypatch.setattr(core_config, "load_role_grants", lambda: stripped)
    h = org.headers(org.member)
    own = f"{PREFIX}/preferences/{org.member.id}"
    assert client.get(own, headers=h).status_code == 403
    body = {"channels": {"transactional": [], "reminder": []}}  # the body test_api's owner update gets a 200 for
    assert client.put(own, json=body, headers=h).status_code == 403
    assert client.get(f"{PREFIX}/inbox", headers=h).status_code == 403
    assert client.post(f"{PREFIX}/inbox/{uuid.uuid4()}/read", headers=h).status_code == 403


def test_a_caller_outside_any_organisation_is_still_refused_even_holding_the_self_keys(client, db):
    """organisation=True keeps what require_organisation guaranteed before: own resources belong to an
    organisation user."""
    with platform_scope():
        user = create_user(
            db, organisation_id=None, email="no-org@platform.example", name="n", password="Secret123!", roles=["member"]
        )
        db.commit()
    h = auth(create_token(user_id=user.id, organisation_id=None, roles=["member"]))
    assert client.get(f"{PREFIX}/inbox", headers=h).status_code == 403
    assert client.get(f"{PREFIX}/preferences/{user.id}", headers=h).status_code == 403


# --- the in-process path -------------------------------------------------------------------------------


def _messages(db, org, as_org) -> list[Message]:
    with as_org(org):
        return db.scalars(select(Message).where(Message.organisation_id == org.id)).all()


def _caller_work(db, org, as_org) -> None:
    """Stands in for the caller's own pending work, such as tenancy's registration rows."""
    with as_org(org):
        events.publish(db, "test.caller.recorded", org.id, {"n": 1})


def _caller_events(db, org) -> list[str]:
    return outbox_names(db, org.id, prefix="test.")


def test_accept_in_transaction_rides_the_callers_transaction(db, org, as_org):
    _caller_work(db, org, as_org)
    with as_org(org):
        accepted = messages.accept_in_transaction(db, **reminder_request())
    assert accepted.created
    db.rollback()  # the caller abandons its work: the message goes with it
    assert _messages(db, org, as_org) == [] and _caller_events(db, org) == []


def test_a_rollback_undoes_the_message_even_when_it_is_the_callers_first_write(db, org, as_org):
    """Regression: on SQLite the savepoint accept_message takes, if it came before any write, was the outermost
    transaction itself, and releasing it committed the message. The caller's rollback then left it behind."""
    with as_org(org):
        messages.accept_in_transaction(db, **reminder_request())  # no caller work written before this
    db.rollback()
    assert _messages(db, org, as_org) == []


def test_the_message_commits_together_with_the_callers_work(db, org, as_org):
    _caller_work(db, org, as_org)
    with as_org(org):
        messages.accept_in_transaction(db, **reminder_request())
    db.commit()
    assert len(_messages(db, org, as_org)) == 1 and _caller_events(db, org) == ["test.caller.recorded"]


def test_nothing_is_sent_before_the_caller_delivers(db, org, as_org):
    t = ScriptedTransport()
    with as_org(org):
        messages.accept_in_transaction(db, transport=t, **reminder_request())
    db.commit()
    assert t.sent == [] and _messages(db, org, as_org)[0].status == "queued"


def test_a_replay_leaves_the_callers_pending_work_alone(db, org, as_org):
    """send_message would roll the session back on a replay, discarding the caller's uncommitted work. The
    in-process step must not."""
    request = reminder_request()
    with as_org(org):
        first, _ = messages.send_message(db, transport=ScriptedTransport(), **request)
    _caller_work(db, org, as_org)
    with as_org(org):
        again = messages.accept_in_transaction(db, **request)
    assert not again.created and again.message.id == first.id
    db.commit()
    assert _caller_events(db, org) == ["test.caller.recorded"] and len(_messages(db, org, as_org)) == 1


def test_send_message_still_owns_the_transaction_which_is_why_callers_must_not_use_it(db, org, as_org):
    request = reminder_request()
    with as_org(org):
        messages.send_message(db, transport=ScriptedTransport(), **request)
    _caller_work(db, org, as_org)
    with as_org(org):
        messages.send_message(db, transport=ScriptedTransport(), **request)  # a replay: rolls the session back
    db.commit()
    assert _caller_events(db, org) == []


def test_no_transport_is_refused_before_writing_and_the_caller_decides(db, org, as_org, monkeypatch):
    monkeypatch.setenv("NOTIFICATION_TRANSPORT", "adapter")
    monkeypatch.setenv("NOTIFICATION_ADAPTER", "not-installed")
    _caller_work(db, org, as_org)
    with pytest.raises(NotificationError) as e, as_org(org):
        messages.accept_in_transaction(db, **reminder_request())
    assert e.value.status == 503
    db.commit()  # this caller chooses to keep its own work anyway
    assert _messages(db, org, as_org) == [] and _caller_events(db, org) == ["test.caller.recorded"]


def test_deliver_sends_once_with_the_secret_after_the_caller_commits(db, org, as_org):
    t = ScriptedTransport()
    request = verify_request()
    with as_org(org):
        accepted = messages.accept_in_transaction(db, transport=t, **request)
    assert accepted.message.status == "queued"  # accepted is recorded, not sent
    db.commit()
    message = messages.deliver_accepted(accepted)
    messages.deliver_accepted(accepted)  # a second call must not send again
    assert len(t.sent) == 1 and request["variables"]["token"] in t.sent[0].body
    assert message.status == "sent" and "token" not in (message.variables or {})  # the secret is never stored


def test_deliver_before_the_caller_commits_finds_nothing_sends_nothing_and_commits_nothing(db, org, as_org):
    """deliver_accepted works in its own session, where an uncommitted row does not exist. Called too early it
    refuses, and the caller's unfinished work is not committed behind its back."""
    t = ScriptedTransport()
    _caller_work(db, org, as_org)
    with as_org(org):
        accepted = messages.accept_in_transaction(db, transport=t, **reminder_request())
    with pytest.raises(NotificationError) as e:
        messages.deliver_accepted(accepted)
    assert e.value.status == 404 and t.sent == []
    db.rollback()  # the caller abandons its work: nothing of it, or of the message, was committed
    assert _messages(db, org, as_org) == [] and _caller_events(db, org) == []


def test_deliver_after_the_caller_rolled_back_sends_nothing(db, org, as_org):
    t = ScriptedTransport()
    with as_org(org):
        accepted = messages.accept_in_transaction(db, transport=t, **reminder_request())
    db.rollback()
    with pytest.raises(NotificationError) as e:
        messages.deliver_accepted(accepted)
    assert e.value.status == 404 and t.sent == []


def test_a_retryable_failure_is_reported_as_not_delivered(db, org, as_org):
    t = ScriptedTransport(SendResult(False, reason="transport_unavailable", retryable=True))
    with as_org(org):
        accepted = messages.accept_in_transaction(db, transport=t, **reminder_request())
    db.commit()
    message = messages.deliver_accepted(accepted)
    assert len(t.sent) == 1
    assert message.status == "queued" and message.next_attempt_at is not None
    assert message.last_error == "transport_unavailable"


def test_delivering_a_replay_sends_nothing(db, org, as_org):
    request = reminder_request()
    with as_org(org):
        messages.send_message(db, transport=ScriptedTransport(), **request)
        replay = messages.accept_in_transaction(db, **request)
    t = ScriptedTransport()
    replay.transport = t
    messages.deliver_accepted(replay)
    assert t.sent == []


def test_a_secret_bearing_message_dispatched_without_its_secret_fails_rather_than_sends(db, org, as_org):
    """One of the two places secret_unavailable is set: dispatch() given a queued message whose template carries
    a secret, without that secret. It cannot re-render it, so it fails it."""
    t = ScriptedTransport()
    with as_org(org):
        accepted = messages.accept_in_transaction(db, transport=t, **verify_request())
    db.commit()
    with as_org(org):
        message = messages.dispatch(db, accepted.message.id, transport=t)
    assert message.status == "failed" and message.last_error == "secret_unavailable" and t.sent == []


def _after_a_crash() -> datetime:
    """created_at comes from the real clock, so "queued longer than the sending lease" needs a real-clock base."""
    return datetime.now(UTC) + timedelta(hours=1)


def test_after_a_crash_before_delivery_recovery_sends_a_message_without_a_secret(db, org, as_org):
    """The caller committed and the process stopped before deliver_accepted. The row holds everything needed,
    so the next sweep sends it. Nothing runs that sweep automatically until the scheduler (#82) exists."""
    t = ScriptedTransport()
    with as_org(org):
        messages.accept_in_transaction(db, transport=t, **reminder_request())
    db.commit()  # ... and the process stops here
    counts = messages.recover_stuck(transport=t, now=_after_a_crash())
    assert counts["redriven"] == 1 and len(t.sent) == 1


def test_after_a_crash_before_delivery_a_message_with_a_secret_is_failed_never_sent(db, org, as_org):
    """The other place secret_unavailable is set: the recovery sweep meeting a queued message whose secret is
    gone. Delivery that survives this is the relay's job (#83), not something recovery can do."""
    t = ScriptedTransport()
    with as_org(org):
        accepted = messages.accept_in_transaction(db, transport=t, **verify_request())
    db.commit()  # ... and the process stops here
    counts = messages.recover_stuck(transport=t, now=_after_a_crash())
    assert counts["failed"] == 1 and t.sent == []
    db.expire_all()  # recovery changed the row in its own session
    with as_org(org):
        row = db.get(Message, accepted.message.id)
    assert row.status == "failed" and row.last_error == "secret_unavailable"


# --- the memory transport no longer needs eos_core.notify ----------------------------------------------


def test_the_memory_transport_records_in_its_own_list_and_leaves_the_legacy_stub_alone():
    """The legacy half runs only while eos_core.notify exists, so this test never blocks its deletion."""
    legacy = importlib.import_module("eos_core.notify") if importlib.util.find_spec("eos_core.notify") else None
    before = list(legacy.sent) if legacy else None
    MemoryTransport().send(
        OutboundMessage(
            message_id="m-1", organisation_id="o-1", channel="email", to="p@college.example.com",
            sender="EOS <no-reply@example.invalid>", subject="s", body="b", dev_secrets={"token": "t-1"},
        )
    )  # fmt: skip
    if legacy is not None:
        assert legacy.sent == before
    assert transport_module.sent[-1] == {
        "to": "p@college.example.com",
        "subject": "s",
        "body": "b",
        "organisation_id": "o-1",
        "message_id": "m-1",
        "token": "t-1",
    }


def test_the_transport_module_does_not_import_eos_core_notify():
    """So deleting eos_core.notify cannot break this module."""
    tree = ast.parse(inspect.getsource(transport_module))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported |= {f"{node.module}.{a.name}" for a in node.names}
        elif isinstance(node, ast.Import):
            imported |= {a.name for a in node.names}
    assert "eos_core.notify" not in imported


# --- the host catalogue --------------------------------------------------------------------------------


def test_notification_is_enabled_in_the_host_catalogue():
    enabled = yaml.safe_load((REPO / "apps/backend/config/modules.enabled.yaml").read_text())
    assert "notification" in enabled["platform"]


def test_the_router_and_chain_sit_where_the_host_loader_looks_for_them():
    """The loader's convention: package eos_<name>, router eos_<name>.api.router:router, chain at <entry>/db."""
    from fastapi import APIRouter

    assert isinstance(importlib.import_module("eos_notification.api.router").router, APIRouter)
    assert (MODULE / "db" / "alembic.ini").is_file()
