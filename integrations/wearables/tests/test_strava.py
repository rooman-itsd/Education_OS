"""Strava through the wearable-data port, against replayed fixtures: OAuth, the activity pull, the rate gate, and the push
subscription, which has no signature (the draft's mitigation is what is tested)."""

from __future__ import annotations

import json
from datetime import timedelta
from urllib.parse import parse_qs, urlsplit

import pytest
from wear_support import (
    STRAVA_ATHLETE,
    STRAVA_SUB,
    STRAVA_VERIFY,
    fixture,
    form_of,
    link_row,
    make_link,
    records,
    request,
)

API = r"https://www\.strava\.com/api/v3"
OAUTH = r"https://www\.strava\.com/oauth"
PERSON = "00000000-0000-4000-8000-0000000000a1"


def test_the_authorize_url_asks_for_activity_read_all_and_has_no_pkce(adapter, org):
    url = adapter.begin_authorisation(
        org.ctx("strava"), {"state": "st", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output["authorize_url"]
    q = parse_qs(urlsplit(url).query)
    assert (
        url.startswith("https://www.strava.com/oauth/authorize?")
        and q["scope"] == ["activity:read_all"]
        and q["state"] == ["st"]
    )
    assert q["client_id"] == ["platform-strava-id"] and q["response_type"] == ["code"] and "code_challenge" not in q


def test_completing_authorisation_names_the_athlete_and_returns_the_tokens(adapter, transport, org):
    transport.on("POST", OAUTH + "/token", "strava/token_exchange.json")
    r = adapter.complete_authorisation(
        org.ctx("strava", secrets={}),
        {"code": "abc", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    )
    assert r.output["provider_subject"] == STRAVA_ATHLETE and r.output["secrets"] == {
        "access_token": "strava-access-1",
        "refresh_token": "strava-refresh-1",
    }
    assert r.output["expires_at"] == "2026-11-09T10:40:00+00:00"
    assert form_of(transport.last("POST", "oauth/token")) == {
        "client_id": "platform-strava-id",
        "client_secret": "platform-strava-secret",
        "code": "abc",
        "grant_type": "authorization_code",
    }


def test_a_refused_code_is_auth_failed(adapter, transport, org):
    transport.on(
        "POST",
        OAUTH + "/token",
        status=400,
        body={"message": "Bad Request", "errors": [{"resource": "RequestToken", "code": "invalid"}]},
    )
    assert (
        adapter.complete_authorisation(
            org.ctx("strava", secrets={}),
            {"code": "bad", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
        ).error["code"]
        == "auth_failed"
    )


def test_refresh_and_a_refused_refresh_which_means_the_athlete_must_link_again(adapter, transport, org):
    transport.on("POST", OAUTH + "/token", "strava/token_refresh.json")
    out = adapter.refresh_authorisation(org.ctx("strava")).output
    assert out["secrets"] == {"access_token": "strava-access-2", "refresh_token": "strava-refresh-2"}
    assert form_of(transport.last("POST", "oauth/token"))["grant_type"] == "refresh_token"
    transport.routes.clear()
    transport.on("POST", OAUTH + "/token", status=400, body={"message": "Bad Request"})
    e = adapter.refresh_authorisation(org.ctx("strava")).error
    assert e["code"] == "consent_required" and e["retryable"] is False


def test_refresh_failure_marks_the_link_expired_for_the_coachs_alerts(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("POST", OAUTH + "/token", status=400, body={})
    adapter.refresh_authorisation(org.ctx("strava", ids["person"], ids["link"]))
    assert link_row(ids["link"]).status == "expired"


def test_revoke_deauthorizes_at_strava(adapter, transport, org):
    transport.on("POST", OAUTH + "/deauthorize", status=200, body={"access_token": "x"})
    assert adapter.revoke_authorisation(org.ctx("strava")).output == {"revoked": True}
    assert form_of(transport.last("POST", "deauthorize")) == {"access_token": "strava-access-1"}


def test_sync_reads_activities_and_normalises_them_to_the_ports_units(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    r = adapter.sync(
        org.ctx("strava", ids["person"], ids["link"]),
        {"account_link_id": ids["link"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    assert r.error is None and r.output == {"stored": 2, "updated": 0, "from": "2026-11-03", "to": "2026-11-05"}
    q = parse_qs(urlsplit(str(transport.last("GET", "athlete/activities").url)).query)
    assert q["after"] == ["1793664000"] and q["before"] == ["1793923200"] and q["per_page"] == ["100"]
    assert transport.last("GET", "athlete/activities").headers["authorization"] == "Bearer strava-access-1"
    run, ride = sorted(records(ids["link"]), key=lambda r: r.provider_record_id)
    assert run.fields == {"provider_activity_id": "9876543210", "sport": "run", "started_at": "2026-11-04T01:00:00+00:00", "duration_s": 2700,
                          "distance_m": 8123.4, "kcal": None, "avg_hr_bpm": 151, "max_hr_bpm": 179, "training_load": 61.0, "hr_zones_s": [], "source": "strava"}  # fmt: skip
    assert ride.fields["kcal"] == 179.3 and ride.fields["sport"] == "ride"  # 750 kJ x 0.239006
    assert run.display_scope == ride.display_scope == "athlete_only"


def test_sync_of_a_type_strava_does_not_have_is_unsupported(adapter, org):
    ids = make_link(org, "strava")
    for t in ("sleep", "daily_summary", "heart_rate_variability", "body_composition"):
        assert (
            adapter.sync(
                org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"], "data_types": [t]}
            ).error["code"]
            == "unsupported"
        )


def test_the_rate_gate_stops_calling_when_a_window_is_used_up_and_says_when_it_reopens(adapter, transport, org, clock):
    ids = make_link(org, "strava")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    transport.on(
        "GET",
        API + r"/athlete/activities",
        status=200,
        body=[],
        headers={"X-ReadRateLimit-Limit": "100,1000", "X-ReadRateLimit-Usage": "100,400"},
    )
    assert adapter.sync(ctx, {"account_link_id": ids["link"]}).error is None
    clock.now = clock.now.replace(minute=7)
    sent = len(transport.requests)
    e = adapter.sync(ctx, {"account_link_id": ids["link"]}).error
    assert e["code"] == "throttled" and e["retryable"] is True and e["retry_after_s"] == 8 * 60  # 06:07 -> 06:15
    assert len(transport.requests) == sent  # nothing was sent
    clock.now = clock.now.replace(minute=15, second=1)
    assert adapter.sync(ctx, {"account_link_id": ids["link"]}).error is None  # the window reopened


def test_a_spent_day_holds_until_midnight_utc(adapter, transport, org):
    ids = make_link(org, "strava")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    transport.on(
        "GET",
        API + r"/athlete/activities",
        status=200,
        body=[],
        headers={"X-ReadRateLimit-Limit": "100,1000", "X-ReadRateLimit-Usage": "5,1000"},
    )
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    assert adapter.sync(ctx, {"account_link_id": ids["link"]}).error["retry_after_s"] == 18 * 3600


def test_a_429_is_throttled_until_the_next_quarter_hour(adapter, transport, org, clock):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", status=429, body={"message": "Rate Limit Exceeded"})
    clock.now = clock.now.replace(minute=44)
    e = adapter.sync(org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"]}).error
    assert e["code"] == "throttled" and e["retry_after_s"] == 60
    assert link_row(ids["link"]).consecutive_failures == 1


def test_a_revoked_token_expires_the_link_and_the_athlete_must_link_again(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", status=401, body={"message": "Authorization Error"})
    e = adapter.sync(org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"]}).error
    assert e["code"] == "consent_required" and link_row(ids["link"]).status == "expired"
    assert (
        adapter.sync(org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"]}).error["code"]
        == "consent_required"
    )


# --- the push subscription: no signature, so identity is the subscription id and an athlete with an active link --------


def event(name: str, **over) -> bytes:
    body = json.loads(fixture(name))
    body.update(over)
    return json.dumps(body).encode()


def verdict(adapter, raw: bytes, ctx=None):
    r = adapter.verify_inbound(ctx, request(raw, query={"provider": "strava"}))
    assert r.error is None
    return r.output


def test_the_handshake_echoes_the_challenge_only_for_our_verify_token(adapter):
    ok = adapter.verify_inbound(
        None,
        request(
            b"",
            method="GET",
            query={
                "provider": "strava",
                "hub.mode": "subscribe",
                "hub.challenge": "15f7d1a91c1f40f8a748fd134752feb3",
                "hub.verify_token": STRAVA_VERIFY,
            },
        ),
    ).output
    assert ok["verdict"] == "handshake" and ok["handshake_response"]["status"] == 200
    assert (
        json.loads(ok["handshake_response"]["body"]) == {"hub.challenge": "15f7d1a91c1f40f8a748fd134752feb3"}
        and ok["handshake_response"]["content_type"] == "application/json"
    )
    for q in (
        {"hub.verify_token": "wrong"},
        {"hub.verify_token": ""},
        {},
        {"hub.mode": "unsubscribe", "hub.verify_token": STRAVA_VERIFY},
    ):
        full = {"provider": "strava", "hub.mode": "subscribe", "hub.challenge": "abc", **q}
        if "hub.verify_token" not in q:
            full.pop("hub.verify_token", None)
        assert adapter.verify_inbound(None, request(b"", method="GET", query=full)).output == {
            "verdict": "reject",
            "reject_status": 403,
        }


@pytest.mark.parametrize("challenge", ["", "a b", "x" * 300, "<script>", "a\nb", "../x"])
def test_a_hostile_challenge_is_not_echoed(adapter, challenge):
    out = adapter.verify_inbound(
        None,
        request(
            b"",
            method="GET",
            query={
                "provider": "strava",
                "hub.mode": "subscribe",
                "hub.challenge": challenge,
                "hub.verify_token": STRAVA_VERIFY,
            },
        ),
    ).output
    assert out["verdict"] == "reject"


def test_without_a_configured_verify_token_no_handshake_answers(adapter, monkeypatch):
    monkeypatch.delenv("WEARABLES_STRAVA_VERIFY_TOKEN")
    assert (
        adapter.verify_inbound(
            None,
            request(
                b"",
                method="GET",
                query={"provider": "strava", "hub.mode": "subscribe", "hub.challenge": "abc", "hub.verify_token": ""},
            ),
        ).output["verdict"]
        == "reject"
    )


def test_an_event_for_our_subscription_and_an_athlete_with_an_active_link_is_accepted(adapter, org):
    make_link(org, "strava")
    v = verdict(adapter, fixture("strava/event_activity_create.json").encode())
    assert v["verdict"] == "accept" and v["resolves_to"] == {
        "connection_id": org.connection_id,
        "account_link_subject": STRAVA_ATHLETE,
    }
    assert v["dedupe_key"] == f"strava:{STRAVA_SUB}:activity:9876543210:create:1793858400"
    assert verdict(adapter, fixture("strava/event_activity_create.json").encode())["dedupe_key"] == v["dedupe_key"]


@pytest.mark.parametrize("change", [
    {"subscription_id": 999}, {"subscription_id": None}, {"owner_id": 1}, {"owner_id": "abc"}, {"owner_id": True}, {"owner_id": "9" * 30}, {"owner_id": None},
    {"object_type": "route"}, {"object_type": None},
])  # fmt: skip
def test_an_event_that_is_not_ours_is_rejected(adapter, org, change):
    make_link(org, "strava")
    assert verdict(adapter, event("strava/event_activity_create.json", **change)) == {
        "verdict": "reject",
        "reject_status": 401,
    }


@pytest.mark.parametrize("status", ["pending", "expired", "revoked", "error"])
def test_an_athlete_whose_link_is_not_active_is_rejected(adapter, org, status):
    make_link(org, "strava", status=status)
    assert verdict(adapter, fixture("strava/event_activity_create.json").encode())["verdict"] == "reject"


def test_another_providers_link_with_the_same_id_does_not_count(adapter, org):
    make_link(org, "polar", subject=STRAVA_ATHLETE)
    assert verdict(adapter, fixture("strava/event_activity_create.json").encode())["verdict"] == "reject"


@pytest.mark.parametrize(
    "raw", [b"", b"x", b"[]", b"null", b"\xff", b"{}", b'{"subscription_id": ' + b"9" * 5000 + b"}"]
)
def test_garbage_is_rejected_not_an_error(adapter, org, raw):
    make_link(org, "strava")
    r = adapter.verify_inbound(None, request(raw, query={"provider": "strava"}))
    assert r.error is None and r.output["verdict"] == "reject"
    assert adapter.parse_inbound(None, request(raw, query={"provider": "strava"})).output == {"notifications": []}


def test_nothing_in_the_body_is_trusted_an_event_only_says_something_changed(adapter, org):
    make_link(org, "strava")
    body = json.loads(fixture("strava/event_activity_create.json"))
    body["updates"] = {"title": "<script>", "distance": 99999999, "sport_type": "Hack"}
    raw = json.dumps(body).encode()
    out = adapter.parse_inbound(None, request(raw, query={"provider": "strava"})).output["notifications"]
    assert out == [
        {
            "port": "wearable-data",
            "kind": "data_available",
            "data": {
                "account_link_subject": STRAVA_ATHLETE,
                "data_types": ["activity"],
                "from": "2026-10-29",
                "to": "2026-11-05",
            },
        }
    ]
    assert records() == []  # parsing stored nothing: the data comes from the athlete's own token in sync


def test_an_update_has_the_same_effect_a_delete_removes_the_record(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    adapter.sync(org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"]})
    assert len(records(ids["link"])) == 2
    update = adapter.parse_inbound(
        None, request(fixture("strava/event_activity_update.json"), query={"provider": "strava"})
    ).output["notifications"]
    assert update[0]["kind"] == "data_available"
    gone = adapter.parse_inbound(
        None, request(fixture("strava/event_activity_delete.json"), query={"provider": "strava"})
    ).output
    assert gone == {"notifications": []} and [r.provider_record_id for r in records(ids["link"])] == ["9876543211"]


def test_deauthorisation_revokes_the_link_and_deletes_the_athletes_strava_data(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    adapter.sync(org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"]})
    out = adapter.parse_inbound(
        None, request(fixture("strava/event_athlete_deauthorized.json"), query={"provider": "strava"})
    ).output["notifications"]
    assert out == [
        {"port": "wearable-data", "kind": "link_revoked_by_provider", "data": {"account_link_subject": STRAVA_ATHLETE}}
    ]
    assert link_row(ids["link"]).status == "revoked" and records(ids["link"]) == []
    assert (
        verdict(adapter, fixture("strava/event_athlete_deauthorized.json").encode())["verdict"] == "reject"
    )  # no longer an active link


def test_other_athlete_updates_are_ignored(adapter, org):
    make_link(org, "strava")
    raw = event("strava/event_athlete_deauthorized.json", updates={"weight": 70})
    assert adapter.parse_inbound(None, request(raw, query={"provider": "strava"})).output == {"notifications": []}
    assert link_row(make_link(org, "strava", subject="777")["link"]).status == "active"


def test_an_event_for_an_athlete_nobody_linked_announces_nothing(adapter, org):
    assert adapter.parse_inbound(
        None, request(fixture("strava/event_activity_create.json"), query={"provider": "strava"})
    ).output == {"notifications": []}


_ = timedelta
