"""Modes (mock, sandbox, live), the start-up refusal, and that no secret ever reaches a log, a repr or an error."""

from __future__ import annotations

import json
import logging
import uuid

import pytest
from eos_wearables.application.adapter import WearablesAdapter, get_adapter, startup_check
from eos_wearables.domain.context import Context
from eos_wearables.domain.errors import AdapterError
from eos_wearables.infrastructure.config import Config
from wear_support import link_input, link_row, make_link, records

PERSON = "00000000-0000-4000-8000-0000000000a1"
PROVIDERS = ("garmin", "polar", "google-health", "strava")


@pytest.mark.parametrize("provider", PROVIDERS)
def test_mock_mode_supports_the_whole_port_and_touches_no_network(adapter, transport, org, provider):
    link = str(uuid.uuid4())
    ctx = org.ctx(provider, PERSON, link, mode="mock", secrets={})
    assert (
        adapter.link_account(ctx, link_input(PERSON, provider, account_link_id=link))
        .output["authorize_url"]
        .startswith("https://mock.")
    )
    done = adapter.complete_authorisation(
        ctx, {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output
    assert done["secrets"]["access_token"] == "mock-access-token" and link_row(link).status == "active"
    assert adapter.healthcheck(ctx).output["status"] == "healthy"
    synced = adapter.sync(ctx, {"account_link_id": link, "from": "2026-11-03", "to": "2026-11-05"})
    assert synced.error is None and synced.output["stored"] > 0 and records(link)
    again = adapter.sync(ctx, {"account_link_id": link, "from": "2026-11-03", "to": "2026-11-05"}).output
    assert again["stored"] == 0 and again["updated"] == 0
    first = records(link)[0]
    got = adapter.read(
        org.ctx(provider, mode="mock"),
        {
            "person_id": PERSON,
            "data_type": first.data_type,
            "from": "2026-11-01",
            "to": "2026-11-05",
            "purpose": "athlete_self",
            "requester_person_id": PERSON,
        },
    )
    assert got.error is None and got.output["items"]
    assert adapter.refresh_authorisation(ctx).output["secrets"] and adapter.revoke_authorisation(ctx).output == {
        "revoked": True
    }
    assert adapter.unlink_account(ctx, {"account_link_id": link}).output["status"] == "revoked" and records(link) == []
    assert not transport.requests


def test_mock_mode_is_the_default_when_neither_the_hub_nor_the_environment_names_a_mode(adapter, transport, org):
    link = make_link(org, "strava")
    r = adapter.sync(
        org.ctx("strava", link["person"], link["link"], mode=None, secrets={}),
        {"account_link_id": link["link"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    assert r.error is None and r.output["stored"] > 0 and not transport.requests


def test_mock_mode_still_verifies_for_real(adapter, org):
    from wear_support import fixture, request

    assert (
        adapter.verify_inbound(org.ctx("polar", mode="mock"), request(fixture("polar/event_exercise.json"), {})).output[
            "verdict"
        ]
        == "reject"
    )


def test_mock_strava_has_activities_only(adapter, org):
    link = make_link(org, "strava")
    ctx = org.ctx("strava", link["person"], link["link"], mode="mock")
    assert adapter.sync(ctx, {"account_link_id": link["link"], "data_types": ["sleep"]}).error["code"] == "unsupported"


def test_the_configured_mode_applies_when_the_hub_names_none(transport, clock, org, monkeypatch):
    monkeypatch.setenv("WEARABLES_MODE", "sandbox")
    a = WearablesAdapter(client_factory=transport.factory(), clock=clock)
    link = make_link(org, "strava")
    transport.on("GET", r"athlete/activities", body=[])
    assert (
        a.sync(org.ctx("strava", link["person"], link["link"], mode=None), {"account_link_id": link["link"]}).error
        is None
    )
    assert transport.sent("GET", "athlete/activities")


def test_a_bad_mode_value_is_not_configured(adapter, org, monkeypatch):
    monkeypatch.setenv("WEARABLES_MODE", "production")
    link = make_link(org, "strava")
    assert (
        adapter.sync(
            org.ctx("strava", link["person"], link["link"], mode=None), {"account_link_id": link["link"]}
        ).error["code"]
        == "not_configured"
    )


def test_live_refuses_to_start_without_its_credentials(monkeypatch):
    for k in ("GARMIN_CLIENT_SECRET", "POLAR_WEBHOOK_SIGNATURE_KEY", "GOOGLE_HEALTH_SCOPES", "STRAVA_VERIFY_TOKEN"):
        monkeypatch.delenv("WEARABLES_" + k)
    monkeypatch.setenv("WEARABLES_MODE", "live")
    with pytest.raises(AdapterError) as e:
        get_adapter()
    assert e.value.code == "not_configured"
    for need in (
        "WEARABLES_GARMIN_CLIENT_SECRET",
        "WEARABLES_POLAR_WEBHOOK_SIGNATURE_KEY",
        "WEARABLES_GOOGLE_HEALTH_SCOPES",
        "WEARABLES_STRAVA_VERIFY_TOKEN",
    ):
        assert need in e.value.detail


def test_live_starts_when_everything_is_set_and_only_checks_the_providers_it_serves(monkeypatch):
    monkeypatch.setenv("WEARABLES_MODE", "live")
    assert get_adapter().describe()["adapter"] == "wearables"
    for k in ("GARMIN_CLIENT_ID", "GOOGLE_HEALTH_CLIENT_ID"):
        monkeypatch.delenv("WEARABLES_" + k)
    with pytest.raises(AdapterError):
        startup_check()
    monkeypatch.setenv("WEARABLES_PROVIDERS", "polar,strava")
    startup_check()  # an academy that serves only Polar and Strava needs neither Garmin's approval nor Google's


def test_sandbox_and_mock_start_regardless_and_each_call_names_what_it_lacks(monkeypatch, adapter, org):
    for k in list(__import__("os").environ):
        if k.startswith("WEARABLES_") and k != "WEARABLES_MODE":
            monkeypatch.delenv(k)
    monkeypatch.setenv("WEARABLES_MODE", "sandbox")
    startup_check()
    h = adapter.healthcheck(org.ctx("strava")).output
    assert h["status"] == "auth_failed" and "WEARABLES_STRAVA_CLIENT_ID" in h["detail"]
    assert (
        adapter.begin_authorisation(
            org.ctx("strava"), {"state": "s", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
        ).error["code"]
        == "not_configured"
    )


SECRETS = ["strava-access-1", "strava-refresh-1", "polar-access-1", "garmin-access-1", "google-access-1", "platform-strava-secret", "platform-polar-secret", "platform-garmin-secret",
           "platform-google-secret", "strava-verify-token", "polar-signature-secret-key"]  # fmt: skip


def test_no_secret_reaches_the_log_a_repr_or_an_error(adapter, transport, org, caplog):
    caplog.set_level(logging.DEBUG)
    link = make_link(org, "strava")
    transport.on(
        "GET", r"athlete/activities", status=500, body={"message": "strava-access-1 appears in this provider message"}
    )
    transport.on("POST", r"oauth/token", status=400, body={"message": "strava-refresh-1 in the message"})
    results = [
        adapter.sync(org.ctx("strava", link["person"], link["link"]), {"account_link_id": link["link"]}),
        adapter.refresh_authorisation(org.ctx("strava")),
        adapter.begin_authorisation(
            org.ctx("strava"), {"state": "s", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
        ),
        adapter.verify_inbound(
            None,
            {
                "method": "GET",
                "query": {
                    "provider": "strava",
                    "hub.mode": "subscribe",
                    "hub.challenge": "abc",
                    "hub.verify_token": "wrong",
                },
                "headers": {},
                "raw_body": b"",
            },
        ),
    ]
    dump = (
        json.dumps([r.to_dict() for r in results], default=str)
        + repr(Context.coerce(org.ctx("strava")))
        + caplog.text
        + repr(Config.load())
        + Config.load().describe()
    )
    for secret in SECRETS:
        assert secret not in dump, secret
    assert "appears in this provider message" not in dump and "in the message" not in dump
