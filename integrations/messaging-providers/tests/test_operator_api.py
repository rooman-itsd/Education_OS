"""The operator API in contracts/openapi.yaml: who may call what, that no credential ever comes back, that health
never sends, and that the test send cannot be turned into a way of sending mail."""

from __future__ import annotations

import logging
import uuid

import pytest
from eos_core.config import load_role_grants, permissions_for
from eos_core.security import create_token
from eos_messaging_providers.api.router import ADMIN, READ, router
from eos_messaging_providers.application import providers, registry
from eos_messaging_providers.infrastructure.smtp import SmtpEmailProvider
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from smtp_support import CONFIG, FakeSmtp

PREFIX = "/api/v1/messaging-providers"
ADDRESS = "operator@college.example.com"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


SUPER_ADMIN_ID = str(uuid.uuid4())
SUPER_ADMIN = auth(create_token(user_id=SUPER_ADMIN_ID, organisation_id=None, roles=["super-admin"], super_admin=True))
ORG_ADMIN = auth(create_token(user_id=str(uuid.uuid4()), organisation_id=str(uuid.uuid4()), roles=["org-admin"]))


@pytest.fixture(scope="module")
def client():
    """The adapter alone, as module-standard rule 6 asks: no host and no other module."""
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def server(monkeypatch):
    """Every provider the API builds talks to a fake server, and the process-local state starts empty."""
    fake = FakeSmtp()
    monkeypatch.setitem(
        registry.EMAIL_PROVIDERS, "smtp", lambda: SmtpEmailProvider(config=CONFIG, client_factory=lambda _c: fake)
    )
    for key in ("MESSAGING_PROVIDERS_EMAIL", "MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR"):
        monkeypatch.delenv(key, raising=False)
    providers.test_sends.reset()
    providers._last_health.clear()
    return fake


# --- who may call what -----------------------------------------------------------------------------------


def test_every_route_needs_a_token(client):
    assert client.get(f"{PREFIX}/providers").status_code == 401
    assert client.get(f"{PREFIX}/providers/smtp/health").status_code == 401
    assert client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}).status_code == 401


def test_an_organisation_admin_sees_nothing_because_providers_are_platform_level(client, server):
    assert client.get(f"{PREFIX}/providers", headers=ORG_ADMIN).status_code == 403
    assert client.get(f"{PREFIX}/providers/smtp/health", headers=ORG_ADMIN).status_code == 403
    assert client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}, headers=ORG_ADMIN).status_code == 403
    assert server.sent == [] and server.noops == 0


def test_the_super_admin_holds_both_keys_through_the_catalogue():
    """Before the super-admin role was added to contracts/permissions.yaml, nobody held the admin key: a super
    admin is given only the platform: keys some role grants."""
    assert {READ, ADMIN} <= permissions_for(["super-admin"], super_admin=True)


def test_no_role_but_the_super_admin_holds_either_key():
    """Blocks are named with platform role ids; a block named for a role no profile assigns would grant nothing."""
    assert {role for role, keys in load_role_grants().items() if keys & {READ, ADMIN}} == {"super-admin"}


def test_every_route_names_its_permission_so_the_host_can_check_coverage_once_mounted():
    for route in router.routes:
        assert isinstance(route, APIRoute)
        keys = {getattr(d.call, "permission", None) for d in route.dependant.dependencies} - {None}
        assert keys <= {READ, ADMIN} and len(keys) == 1, route.path


# --- GET /providers --------------------------------------------------------------------------------------


def test_the_list_shows_smtp_selected_for_email_with_its_capabilities(client):
    body = client.get(f"{PREFIX}/providers", headers=SUPER_ADMIN).json()
    (smtp,) = body["items"]
    assert smtp["id"] == "smtp" and smtp["channel"] == "email" and smtp["enabled"] is True
    assert smtp["capabilities"]["supports_html"] is True and smtp["capabilities"]["supports_reply_to"] is True
    assert smtp["last_health"] is None


def test_a_provider_the_environment_does_not_select_is_listed_as_not_enabled(client, monkeypatch):
    monkeypatch.setenv("MESSAGING_PROVIDERS_EMAIL", "ses")
    (smtp,) = client.get(f"{PREFIX}/providers", headers=SUPER_ADMIN).json()["items"]
    assert smtp["enabled"] is False


def test_no_credential_or_host_ever_comes_back(client, monkeypatch):
    """The contract: credentials are never returned, in any form, masked or otherwise."""
    for key, value in {
        "MESSAGING_PROVIDERS_SMTP_HOST": "relay.secret-host.example",
        "MESSAGING_PROVIDERS_SMTP_USERNAME": "mailer-account",
        "MESSAGING_PROVIDERS_SMTP_PASSWORD": "hunter2-real-password",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.setitem(registry.EMAIL_PROVIDERS, "smtp", SmtpEmailProvider)  # the real config, from the env
    text = client.get(f"{PREFIX}/providers", headers=SUPER_ADMIN).text
    for leaked in ("relay.secret-host.example", "mailer-account", "hunter2-real-password"):
        assert leaked not in text


# --- GET /providers/{provider}/health --------------------------------------------------------------------


def test_health_reports_reachable_and_never_sends(client, server):
    body = client.get(f"{PREFIX}/providers/smtp/health", headers=SUPER_ADMIN).json()
    assert body["reachable"] is True and body["checked_at"]
    assert server.noops == 1 and server.sent == []


def test_the_last_health_result_appears_in_the_list(client):
    checked = client.get(f"{PREFIX}/providers/smtp/health", headers=SUPER_ADMIN).json()
    (smtp,) = client.get(f"{PREFIX}/providers", headers=SUPER_ADMIN).json()["items"]
    assert smtp["last_health"] == {"reachable": True, "checked_at": checked["checked_at"]}


def test_an_unreachable_provider_is_reported_not_raised(client, monkeypatch):
    def down(_config):
        raise ConnectionRefusedError("no listener")

    monkeypatch.setitem(registry.EMAIL_PROVIDERS, "smtp", lambda: SmtpEmailProvider(config=CONFIG, client_factory=down))
    response = client.get(f"{PREFIX}/providers/smtp/health", headers=SUPER_ADMIN)
    assert response.status_code == 200 and response.json()["reachable"] is False


def test_health_for_an_unknown_provider_is_a_404(client):
    assert client.get(f"{PREFIX}/providers/sendgrid/health", headers=SUPER_ADMIN).status_code == 404


# --- POST /providers/{provider}/test ---------------------------------------------------------------------


def test_a_test_send_delivers_one_message_from_the_configured_identity(client, server):
    response = client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}, headers=SUPER_ADMIN)
    assert response.status_code == 202
    body = response.json()
    assert body["accepted"] is True and body["provider_message_id"] and body["reason"] is None
    (sent,) = server.sent
    assert sent["To"] == ADDRESS and sent["Subject"] == providers.TEST_SUBJECT
    assert sent["From"] == "Education OS <no-reply@example.invalid>"


def test_a_refused_test_send_comes_back_as_a_port_reason(client, server):
    response = client.post(f"{PREFIX}/providers/smtp/test", json={"to": f"{ADDRESS}\r\nBcc: x@else.example"},
                           headers=SUPER_ADMIN)  # fmt: skip
    assert response.status_code == 202
    assert response.json() == {"accepted": False, "provider_message_id": None, "reason": "invalid_recipient"}
    assert server.sent == []


def test_the_hourly_limit_stops_the_endpoint_being_used_to_send_mail(client, server, monkeypatch):
    monkeypatch.setenv("MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR", "2")
    codes = [
        client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}, headers=SUPER_ADMIN).status_code
        for _ in range(3)
    ]
    assert codes == [202, 202, 429]
    assert len(server.sent) == 2


def test_a_refused_attempt_still_counts_so_addresses_cannot_be_probed_past_the_limit(client, monkeypatch):
    monkeypatch.setenv("MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR", "1")
    client.post(f"{PREFIX}/providers/smtp/test", json={"to": "bad\r\naddress"}, headers=SUPER_ADMIN)
    assert client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}, headers=SUPER_ADMIN).status_code == 429


def test_a_limit_of_zero_turns_test_sends_off(client, server, monkeypatch):
    monkeypatch.setenv("MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR", "0")
    assert client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}, headers=SUPER_ADMIN).status_code == 429
    assert server.sent == []


def test_asking_for_an_unknown_provider_does_not_use_up_a_send(client, monkeypatch):
    monkeypatch.setenv("MESSAGING_PROVIDERS_TEST_SEND_PER_HOUR", "1")
    assert client.post(f"{PREFIX}/providers/nope/test", json={"to": ADDRESS}, headers=SUPER_ADMIN).status_code == 404
    assert client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}, headers=SUPER_ADMIN).status_code == 202


def test_the_window_slides_so_sends_come_back_after_an_hour():
    now = [0.0]
    window = providers._Window(clock=lambda: now[0])
    assert window.take(1) and not window.take(1)
    now[0] = providers.WINDOW_S - 1
    assert not window.take(1)
    now[0] = providers.WINDOW_S
    assert window.take(1)


@pytest.mark.parametrize("to", ["", "x" * 321])
def test_the_address_is_validated_before_anything_is_sent(client, server, to):
    response = client.post(f"{PREFIX}/providers/smtp/test", json={"to": to}, headers=SUPER_ADMIN)
    assert response.status_code == 422 and server.sent == []


def test_every_test_send_is_recorded_with_who_and_never_the_address(client, caplog):
    with caplog.at_level(logging.INFO, logger="eos.messaging_providers.audit"):
        client.post(f"{PREFIX}/providers/smtp/test", json={"to": ADDRESS}, headers=SUPER_ADMIN)
    (record,) = [r.getMessage() for r in caplog.records if r.name == "eos.messaging_providers.audit"]
    assert SUPER_ADMIN_ID in record and "provider=smtp" in record and "accepted=True" in record
    assert ADDRESS not in record
