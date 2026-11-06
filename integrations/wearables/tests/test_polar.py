"""Polar AccessLink through the wearable-data port, against replayed fixtures."""

from __future__ import annotations

import json
from datetime import date
from urllib.parse import parse_qs, urlsplit

import pytest
from wear_support import POLAR_KEY, body_of, fixture, form_of, make_link, polar_signature, records, request

API = r"https://www\.polaraccesslink\.com/v3"
PERSON = "00000000-0000-4000-8000-0000000000a1"
QS = {"provider": "polar"}


def test_authorize_url(adapter, org):
    url = adapter.begin_authorisation(
        org.ctx("polar"), {"state": "st", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output["authorize_url"]
    q = parse_qs(urlsplit(url).query)
    assert (
        url.startswith("https://flow.polar.com/oauth2/authorization?")
        and q["client_id"] == ["platform-polar-id"]
        and q["state"] == ["st"]
    )


def test_completion_uses_basic_auth_names_the_user_and_registers_them_with_our_member_id(adapter, transport, org):
    person, link = PERSON, "11111111-1111-4111-8111-111111111111"
    transport.on("POST", r"polarremote\.com/v2/oauth2/token", "polar/token.json")
    transport.on("POST", API + "/users$", status=200, body={"polar-user-id": 475, "member-id": person})
    r = adapter.complete_authorisation(
        org.ctx("polar", person, link, secrets={}),
        {"code": "c1", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    )
    assert (
        r.error is None
        and r.output["provider_subject"] == "475"
        and r.output["secrets"] == {"access_token": "polar-access-1"}
        and r.output["expires_at"] is None
    )
    tok = transport.last("POST", "oauth2/token")
    assert tok.headers["authorization"].startswith("Basic ") and form_of(tok)["grant_type"] == "authorization_code"
    reg = transport.last("POST", "/users$")
    assert body_of(reg) == {"member-id": person} and reg.headers["authorization"] == "Bearer polar-access-1"


def test_a_409_on_registration_is_success(adapter, transport, org):
    transport.on("POST", r"polarremote\.com/v2/oauth2/token", "polar/token.json")
    transport.on("POST", API + "/users$", status=409, body={"error": {"message": "already registered"}})
    r = adapter.complete_authorisation(
        org.ctx("polar", PERSON, "22222222-2222-4222-8222-222222222222", secrets={}),
        {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    )
    assert r.error is None


def test_polar_tokens_do_not_expire_so_refresh_is_nothing_to_do(adapter, org):
    assert adapter.refresh_authorisation(org.ctx("polar")).output == {"secrets": {}, "expires_at": None}


def test_revoke_deregisters_the_user(adapter, transport, org):
    transport.on("DELETE", API + "/users/475", status=204)
    assert adapter.revoke_authorisation(org.ctx("polar", PERSON, "33333333-3333-4333-8333-333333333333")).output == {
        "revoked": True
    }
    assert adapter.revoke_authorisation(org.ctx("polar")).output == {
        "revoked": False
    }  # no user id known: nothing to call


def sync(adapter, org, ids, **over):
    return adapter.sync(
        org.ctx("polar", ids["person"], ids["link"]),
        {"account_link_id": ids["link"], "from": "2026-11-03", "to": "2026-11-05", **over},
    )


def test_exercises_are_normalised_with_zones_in_order_and_old_ones_left_out(adapter, transport, org):
    ids = make_link(org, "polar")
    transport.on("GET", API + r"/exercises", "polar/exercises.json")
    r = sync(adapter, org, ids, data_types=["activity"])
    assert r.error is None and r.output["stored"] == 1
    (rec,) = records(ids["link"])
    assert rec.fields == {"provider_activity_id": "aQlC83", "sport": "running", "started_at": "2026-11-04T06:00:00+00:00", "duration_s": 2712, "distance_m": 8500.5, "kcal": 530.0,
                          "avg_hr_bpm": 152, "max_hr_bpm": 181, "training_load": 118.5, "hr_zones_s": [330, 600, 1200], "source": "polar"}  # fmt: skip


def test_daily_activity_and_sleep(adapter, transport, org):
    ids = make_link(org, "polar")
    transport.on("GET", API + r"/users/activities", "polar/activities.json")
    transport.on("GET", API + r"/users/sleep", "polar/sleep.json")
    r = sync(adapter, org, ids, data_types=["daily_summary", "sleep"])
    assert r.error is None and r.output["stored"] == 3
    q = parse_qs(urlsplit(str(transport.last("GET", "users/activities").url)).query)
    assert q == {"from": ["2026-11-03"], "to": ["2026-11-05"]}
    by = {(r.data_type, r.fields["date"]): r.fields for r in records(ids["link"])}
    assert by[("daily_summary", "2026-11-04")] == {"date": "2026-11-04", "steps": 11234, "distance_m": 8421.5, "active_kcal": 640.0, "resting_hr_bpm": None, "avg_hr_bpm": None,
                                                   "max_hr_bpm": None, "active_seconds": 7800, "stress_avg": None, "source": "polar"}  # fmt: skip
    s = by[("sleep", "2026-11-04")]
    assert (s["total_s"], s["deep_s"], s["light_s"], s["rem_s"], s["awake_s"], s["score"]) == (
        26100,
        5400,
        14400,
        6300,
        1800,
        84,
    )
    assert s["started_at"] == "2026-11-03T17:00:00+00:00" and s["ended_at"] == "2026-11-04T00:45:00+00:00"


def test_an_empty_204_is_nothing_new(adapter, transport, org):
    ids = make_link(org, "polar")
    transport.on("GET", API + r"/exercises", status=204)
    assert sync(adapter, org, ids, data_types=["activity"]).output["stored"] == 0


def test_hrv_and_body_composition_are_unsupported(adapter, org):
    ids = make_link(org, "polar")
    for t in ("heart_rate_variability", "body_composition"):
        assert sync(adapter, org, ids, data_types=[t]).error["code"] == "unsupported"
    assert (
        adapter.request_backfill(org.ctx("polar", ids["person"], ids["link"]), {"account_link_id": ids["link"]}).error[
            "code"
        ]
        == "unsupported"
    )
    assert adapter.capabilities(org.ctx("polar")).output["capabilities"] == {
        "data_types": ["daily_summary", "activity", "sleep"], "push": True, "backfill_days": 0, "rate_limit": "500 + 20 per user per 15 min, 5000 + 100 per user per 24 h",
        "requires_mobile_app": False, "display_to_others_allowed": True,
    }  # fmt: skip


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (401, "consent_required"),
        (403, "consent_required"),
        (429, "throttled"),
        (500, "provider_error"),
        (503, "provider_error"),
    ],
)
def test_error_mapping(adapter, transport, org, status, code):
    ids = make_link(org, "polar")
    transport.on(
        "GET",
        API + r"/exercises",
        status=status,
        body={"error": "x"},
        headers={"retry-after": "9"} if status == 429 else {},
    )
    e = sync(adapter, org, ids, data_types=["activity"]).error
    assert e["code"] == code and (e["retry_after_s"] == 9 if status == 429 else True)


# --- webhook ----------------------------------------------------------------------------------------------------


def verify(adapter, raw: bytes, headers: dict | None):
    r = adapter.verify_inbound(None, request(raw, headers if headers is not None else polar_signature(raw), query=QS))
    assert r.error is None
    return r.output


def test_a_correctly_signed_event_is_accepted(adapter, org):
    make_link(org, "polar")
    raw = fixture("polar/event_exercise.json").encode()
    v = verify(adapter, raw, None)
    assert v["verdict"] == "accept" and v["resolves_to"] == {
        "connection_id": org.connection_id,
        "account_link_subject": "475",
    }
    assert (
        polar_signature(raw)["Polar-Webhook-Signature"]
        == __import__("hmac").new(POLAR_KEY.encode(), raw, __import__("hashlib").sha256).hexdigest()
    )


def test_the_ping_sent_when_the_webhook_is_created_is_accepted_and_does_nothing(adapter):
    raw = fixture("polar/event_ping.json").encode()
    assert verify(adapter, raw, None)["verdict"] == "accept"
    assert adapter.parse_inbound(None, request(raw, query=QS)).output == {"notifications": []}


@pytest.mark.parametrize("variant", ["tampered", "wrong_key", "missing", "empty", "not_hex", "other_algorithm"])
def test_events_that_do_not_verify_are_rejected(adapter, org, variant):
    make_link(org, "polar")
    raw = fixture("polar/event_exercise.json").encode()
    headers = polar_signature(raw)
    if variant == "tampered":
        raw = raw.replace(b"475", b"476")
    elif variant == "wrong_key":
        headers = polar_signature(raw, "other-key")
    elif variant == "missing":
        headers = {}
    elif variant == "empty":
        headers = {"Polar-Webhook-Signature": ""}
    elif variant == "not_hex":
        headers = {"Polar-Webhook-Signature": "zz" * 32}
    elif variant == "other_algorithm":
        headers = {
            "Polar-Webhook-Signature": __import__("hmac")
            .new(POLAR_KEY.encode(), raw, __import__("hashlib").sha1)
            .hexdigest()
        }  # noqa: S324
    assert verify(adapter, raw, headers) == {"verdict": "reject", "reject_status": 401}


def test_header_names_are_case_insensitive_and_a_missing_key_verifies_nothing(adapter, org, monkeypatch):
    raw = fixture("polar/event_exercise.json").encode()
    sig = polar_signature(raw)["Polar-Webhook-Signature"]
    assert verify(adapter, raw, {"polar-webhook-signature": sig})["verdict"] == "accept"
    monkeypatch.delenv("WEARABLES_POLAR_WEBHOOK_SIGNATURE_KEY")
    assert verify(adapter, raw, {"polar-webhook-signature": sig})["verdict"] == "reject"


@pytest.mark.parametrize(("name", "data_type", "start"), [("polar/event_exercise.json", "activity", "2026-11-03"), ("polar/event_sleep.json", "sleep", "2026-11-03"),
                                                          ("polar/event_activity_summary.json", "daily_summary", "2026-11-03")])  # fmt: skip
def test_events_announce_that_data_is_available_for_the_link(adapter, org, name, data_type, start):
    make_link(org, "polar")
    out = adapter.parse_inbound(None, request(fixture(name), query=QS)).output["notifications"]
    assert out == [
        {
            "port": "wearable-data",
            "kind": "data_available",
            "data": {"account_link_subject": "475", "data_types": [data_type], "from": start, "to": "2026-11-04"},
        }
    ]
    assert records() == []  # the hub then runs sync, which fetches with the athlete's token


def test_an_event_for_a_user_without_an_active_link_announces_nothing(adapter, org):
    assert adapter.parse_inbound(None, request(fixture("polar/event_exercise.json"), query=QS)).output == {
        "notifications": []
    }


def test_unknown_events_are_ignored(adapter, org):
    make_link(org, "polar")
    raw = json.dumps({"event": "CONTINUOUS_HEART_RATE", "user_id": 475, "timestamp": "2026-11-04T08:00:00Z"})
    assert adapter.parse_inbound(None, request(raw, query=QS)).output == {"notifications": []}


_ = date
