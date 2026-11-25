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
# What Strava answers when the athlete's refresh token is dead, and when it is our own client secret it refuses.
DEAD_REFRESH_TOKEN = {
    "message": "Bad Request",
    "errors": [{"resource": "RefreshToken", "field": "refresh_token", "code": "invalid"}],
}
OUR_CLIENT_SECRET = {
    "message": "Bad Request",
    "errors": [{"resource": "Application", "field": "client_secret", "code": "invalid"}],
}
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
    ctx = org.ctx("strava", ids["person"], ids["link"])
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    assert len(records(ids["link"])) == 2
    update = adapter.parse_inbound(
        None, request(fixture("strava/event_activity_update.json"), query={"provider": "strava"})
    ).output["notifications"]
    assert update[0]["kind"] == "data_available"
    transport.on("GET", API + r"/activities/9876543210", status=404)
    gone = adapter.parse_inbound(
        None, request(fixture("strava/event_activity_delete.json"), query={"provider": "strava"})
    ).output
    assert gone == {"notifications": []} and [r.provider_record_id for r in records(ids["link"])] == ["9876543211"]


def test_deauthorisation_revokes_the_link_and_deletes_the_athletes_strava_data(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    transport.on("GET", API + r"/athlete", status=401)
    transport.on(
        "POST",
        r"oauth/token",
        status=400,
        body={"message": "Bad Request", "errors": [{"field": "refresh_token", "code": "invalid"}]},
    )
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


def test_forged_deauthorisation_without_tokens_is_ignored(adapter, transport, org):
    ids = make_link(org, "strava", tokens={})
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    assert len(records(ids["link"])) == 2
    out = adapter.parse_inbound(
        None, request(fixture("strava/event_athlete_deauthorized.json"), query={"provider": "strava"})
    ).output
    assert out == {"notifications": []}
    assert link_row(ids["link"]).status == "active" and len(records(ids["link"])) == 2


def test_forged_deauthorisation_when_athlete_is_still_authorized_is_ignored(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    transport.on("GET", API + r"/athlete", status=200, body={"id": 12345678})
    out = adapter.parse_inbound(
        None, request(fixture("strava/event_athlete_deauthorized.json"), query={"provider": "strava"})
    ).output
    assert out == {"notifications": []}
    row = link_row(ids["link"])
    assert row.status == "active" and len(records(ids["link"])) == 2


def test_forged_deauthorisation_when_access_token_expired_but_refresh_succeeds_is_ignored(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    transport.on("GET", API + r"/athlete", status=401)
    transport.on(
        "POST",
        r"oauth/token",
        status=200,
        body={"access_token": "new-tok", "refresh_token": "new-ref", "expires_in": 21600},
    )
    out = adapter.parse_inbound(
        None, request(fixture("strava/event_athlete_deauthorized.json"), query={"provider": "strava"})
    ).output
    assert out == {"notifications": []}
    row = link_row(ids["link"])
    assert row.status == "active" and len(records(ids["link"])) == 2
    from eos_wearables.infrastructure import crypto
    from eos_wearables.infrastructure.config import Config

    unsealed = crypto.unseal(Config.load(), row.tokens_encrypted)
    assert json.loads(unsealed)["access_token"] == "new-tok"
    assert json.loads(unsealed)["refresh_token"] == "new-ref"


def test_forged_delete_without_tokens_is_ignored(adapter, transport, org):
    ids = make_link(org, "strava", tokens={})
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    assert len(records(ids["link"])) == 2
    out = adapter.parse_inbound(
        None, request(fixture("strava/event_activity_delete.json"), query={"provider": "strava"})
    ).output
    assert out == {"notifications": []}
    assert len(records(ids["link"])) == 2


def test_forged_delete_when_activity_still_exists_is_ignored(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    ctx = org.ctx("strava", ids["person"], ids["link"])
    adapter.sync(ctx, {"account_link_id": ids["link"]})
    transport.on("GET", API + r"/activities/9876543210", status=200, body={"id": 9876543210})
    out = adapter.parse_inbound(
        None, request(fixture("strava/event_activity_delete.json"), query={"provider": "strava"})
    ).output
    assert out == {"notifications": []}
    assert len(records(ids["link"])) == 2


def test_activity_delete_with_an_expired_token_and_a_dead_refresh_token_is_ignored(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    adapter.sync(org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"]})
    transport.on("GET", API + r"/activities/9876543210", status=401)
    transport.on("POST", r"oauth/token", status=400, body=DEAD_REFRESH_TOKEN)
    out = adapter.parse_inbound(
        None, request(fixture("strava/event_activity_delete.json"), query={"provider": "strava"})
    ).output
    assert out == {"notifications": []}
    assert len(records(ids["link"])) == 2


def test_complete_authorisation_stores_encrypted_tokens(adapter, transport, org):
    from eos_wearables.infrastructure import crypto
    from eos_wearables.infrastructure.config import Config

    transport.on("POST", OAUTH + "/token", "strava/token_exchange.json")
    link_id = "00000000-0000-4000-8000-000000000099"
    person_id = "00000000-0000-4000-8000-000000000098"
    ctx = org.ctx("strava", person_id, link_id, secrets={})
    res = adapter.complete_authorisation(
        ctx,
        {"code": "abc", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    )
    assert res.error is None
    row = link_row(link_id)
    assert row is not None
    assert row.tokens_encrypted is not None
    unsealed = crypto.unseal(Config.load(), row.tokens_encrypted)
    assert json.loads(unsealed)["access_token"] == "strava-access-1"


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


# --- hardening of the confirmation: what a forged event must not be able to do, and what a real one must still do


def _synced(adapter, transport, org, **fields):
    ids = make_link(org, "strava", **fields)
    transport.on("GET", API + r"/athlete/activities", "strava/activities.json")
    adapter.sync(org.ctx("strava", ids["person"], ids["link"]), {"account_link_id": ids["link"]})
    assert len(records(ids["link"])) == 2
    return ids


def _deauthorised(adapter):
    return adapter.parse_inbound(
        None, request(fixture("strava/event_athlete_deauthorized.json"), query={"provider": "strava"})
    )


def _deleted(adapter):
    return adapter.parse_inbound(
        None, request(fixture("strava/event_activity_delete.json"), query={"provider": "strava"})
    )


def _stored(link_id) -> dict:
    from eos_wearables.infrastructure import crypto
    from eos_wearables.infrastructure.config import Config

    return json.loads(crypto.unseal(Config.load(), link_row(link_id).tokens_encrypted))


@pytest.mark.parametrize(
    "status,body",
    [
        (400, OUR_CLIENT_SECRET),
        (401, OUR_CLIENT_SECRET),
        (403, {}),
        (404, {}),
        (400, {}),
        (401, None),
        (400, {"errors": [{"field": "refresh_token", "code": "expired"}]}),
    ],
)
def test_a_token_refusal_that_is_not_about_the_athletes_token_is_not_a_deauthorisation(
    adapter, transport, org, status, body
):
    """A wrong client secret, a wrong URL or an unreadable answer is not the athlete withdrawing the app: a forged event
    must not turn it into the deletion of their data. It is retried, not believed."""
    ids = _synced(adapter, transport, org)
    transport.on("GET", API + r"/athlete$", status=401)
    transport.on("POST", r"oauth/token", status=status, body=body)
    out = _deauthorised(adapter)
    assert out.output is None and out.error["retryable"] is True
    assert link_row(ids["link"]).status == "active" and len(records(ids["link"])) == 2


@pytest.mark.parametrize("status", [429, 500, 502, 503])
def test_strava_failing_or_throttling_confirms_nothing_and_is_retried(adapter, transport, org, status):
    ids = _synced(adapter, transport, org)
    transport.on("GET", API + r"/athlete$", status=status)
    out = _deauthorised(adapter)
    assert out.error["retryable"] is True
    transport.routes.clear()
    transport.on("GET", API + r"/athlete$", status=401)
    transport.on("POST", r"oauth/token", status=status)
    assert _deauthorised(adapter).error["retryable"] is True
    assert link_row(ids["link"]).status == "active" and len(records(ids["link"])) == 2


def test_a_real_deauthorisation_revokes_the_link_deletes_the_data_and_keeps_no_token(adapter, transport, org):
    ids = _synced(adapter, transport, org)
    transport.on("GET", API + r"/athlete$", status=401)
    transport.on("POST", r"oauth/token", status=401, body=DEAD_REFRESH_TOKEN)  # Strava answers 400 or 401 for it
    out = _deauthorised(adapter).output["notifications"]
    assert [n["kind"] for n in out] == ["link_revoked_by_provider"]
    row = link_row(ids["link"])
    assert row.status == "revoked" and records(ids["link"]) == []
    assert row.tokens_encrypted is None


def test_a_link_revoked_by_the_hub_keeps_no_token_either(adapter, transport, org):
    ids = _synced(adapter, transport, org)
    assert link_row(ids["link"]).tokens_encrypted
    adapter.revoke_by_link_id(org.id, ids["link"])
    assert link_row(ids["link"]).tokens_encrypted is None


def test_a_real_delete_with_an_expired_token_is_confirmed_after_a_refresh(adapter, transport, org):
    ids = _synced(adapter, transport, org)
    transport.on("GET", API + r"/activities/9876543210", (401, None, {}, None), (404, None, {}, None))
    transport.on("POST", r"oauth/token", "strava/token_refresh.json")
    assert _deleted(adapter).output == {"notifications": []}
    assert [r.provider_record_id for r in records(ids["link"])] == ["9876543211"]
    assert _stored(ids["link"]) == {"access_token": "strava-access-2", "refresh_token": "strava-refresh-2"}
    assert transport.sent("GET", "activities/9876543210")[-1].headers["authorization"] == "Bearer strava-access-2"


def test_tokens_made_by_a_refresh_are_kept_even_when_the_check_then_fails(adapter, transport, org):
    """Strava may retire the old refresh token when it issues a new one: the new pair is stored before anything else
    can go wrong, or the athlete's link would be lost to a 5xx."""
    ids = _synced(adapter, transport, org)
    transport.on("GET", API + r"/activities/9876543210", (401, None, {}, None), (500, None, {}, None))
    transport.on("POST", r"oauth/token", "strava/token_refresh.json")
    out = _deleted(adapter)
    assert out.error["retryable"] is True and len(records(ids["link"])) == 2
    assert _stored(ids["link"])["refresh_token"] == "strava-refresh-2"


@pytest.mark.parametrize("status", [429, 500, 503])
def test_a_delete_check_that_strava_cannot_answer_is_retried_and_deletes_nothing(adapter, transport, org, status):
    ids = _synced(adapter, transport, org)
    transport.on("GET", API + r"/activities/9876543210", status=status)
    assert _deleted(adapter).error["retryable"] is True
    assert len(records(ids["link"])) == 2


@pytest.mark.parametrize("bad", ["../athlete", "1/../../oauth/x", "12 34", "1e5", "-1", "9" * 21, "", "٣٤٥"])
def test_ids_that_are_not_integers_never_reach_a_url(adapter, transport, org, bad):
    _synced(adapter, transport, org)
    delete = event("strava/event_activity_delete.json", object_id=bad)
    assert verdict(adapter, delete)["verdict"] == "reject"
    assert verdict(adapter, event("strava/event_activity_delete.json", owner_id=bad))["verdict"] == "reject"
    before = len(transport.requests)
    out = adapter.parse_inbound(
        None, request(delete, query={"provider": "strava"})
    ).output  # even if verify were skipped
    assert out == {"notifications": []} and len(transport.requests) == before


def test_a_no_from_strava_holds_the_next_confirmation_for_that_athlete_back(adapter, transport, org, clock):
    """Forged events cost Strava calls: after a 'no', the same athlete is asked again only after the cooldown, and the
    event is retried then, not dropped."""
    _synced(adapter, transport, org)
    transport.on("GET", API + r"/athlete$", status=200, body={"id": 12345678})
    assert _deauthorised(adapter).output == {"notifications": []}
    for _ in range(5):
        held = _deauthorised(adapter)
        assert held.error["code"] == "throttled" and 1 <= held.error["retry_after_s"] <= 30
    assert len(transport.sent("GET", API + r"/athlete$")) == 1
    clock.advance(seconds=31)
    assert _deauthorised(adapter).output == {"notifications": []}
    assert len(transport.sent("GET", API + r"/athlete$")) == 2


def test_a_real_deauthorisation_right_after_a_forged_one_is_retried_not_lost(adapter, transport, org, clock):
    ids = _synced(adapter, transport, org)
    transport.on("GET", API + r"/athlete$", (200, '{"id": 12345678}', {}, None), (401, None, {}, None))
    transport.on("POST", r"oauth/token", status=400, body=DEAD_REFRESH_TOKEN)
    assert _deauthorised(adapter).output == {"notifications": []}  # forged: still authorised
    assert _deauthorised(adapter).error["code"] == "throttled"  # the real one, held back, not believed and not dropped
    clock.advance(seconds=31)
    assert [n["kind"] for n in _deauthorised(adapter).output["notifications"]] == ["link_revoked_by_provider"]
    assert link_row(ids["link"]).status == "revoked"


def test_a_hub_refresh_that_is_refused_is_retried_once_with_the_tokens_kept_here(adapter, transport, org):
    """A confirmation refreshes the token and keeps the new pair here; Strava may retire the old one, which is what the hub
    still holds. The hub's next refresh is refused, and the kept copy is the one that works."""
    ids = make_link(org, "strava", tokens={"access_token": "kept-a", "refresh_token": "kept-r"})
    transport.on("POST", r"oauth/token", (400, "{}", {}, None), (200, fixture("strava/token_refresh.json"), {}, None))
    out = adapter.refresh_authorisation(org.ctx("strava", ids["person"], ids["link"]))
    assert out.error is None and out.output["secrets"]["refresh_token"] == "strava-refresh-2"
    sent = [form_of(r)["refresh_token"] for r in transport.sent("POST", "oauth/token")]
    assert sent == ["strava-refresh-1", "kept-r"]
    assert link_row(ids["link"]).status == "active"


def test_a_hub_refresh_refused_with_nothing_newer_kept_still_expires_the_link(adapter, transport, org):
    ids = make_link(org, "strava")  # kept copy is the hub's own token: nothing newer to try
    transport.on("POST", r"oauth/token", status=400, body={})
    assert (
        adapter.refresh_authorisation(org.ctx("strava", ids["person"], ids["link"])).error["code"] == "consent_required"
    )
    assert len(transport.sent("POST", "oauth/token")) == 1 and link_row(ids["link"]).status == "expired"


def test_a_missing_data_key_stops_a_link_before_the_one_time_code_is_spent(adapter, transport, org, monkeypatch):
    monkeypatch.delenv("WEARABLES_DATA_KEY")
    ids = make_link(org, "strava", tokens={})
    e = adapter.complete_authorisation(
        org.ctx("strava", ids["person"], ids["link"], secrets={}),
        {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    ).error
    assert e["code"] == "not_configured" and transport.requests == []
    refreshed = adapter.refresh_authorisation(org.ctx("strava", ids["person"], ids["link"])).error
    assert refreshed["code"] == "not_configured" and transport.requests == []


def test_the_data_key_can_be_rotated_without_losing_stored_tokens():
    from cryptography.fernet import Fernet
    from eos_wearables.domain.errors import AdapterError
    from eos_wearables.infrastructure import crypto

    old, new = Fernet.generate_key().decode(), Fernet.generate_key().decode()

    def cfg(keys: str):
        return type("C", (), {"data_key": keys, "mode": "sandbox"})()

    sealed = crypto.seal(cfg(old), "tokens")
    assert crypto.unseal(cfg(f"{new},{old}"), sealed) == "tokens"  # the new key first, the old still reads
    assert crypto.unseal(cfg(new), crypto.seal(cfg(f"{new},{old}"), "x")) == "x"  # and the first key is what seals
    with pytest.raises(AdapterError):
        crypto.unseal(cfg(new), sealed)  # once the old key is dropped, what it sealed is unreadable
    with pytest.raises(AdapterError):
        crypto.require_key(cfg(""))
