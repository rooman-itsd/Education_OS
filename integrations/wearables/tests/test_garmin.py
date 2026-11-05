"""Garmin Health API through the wearable-data port: OAuth 2.0 with PKCE, pushed summaries, deregistration and permission
changes, and the Business Enterprise pull and backfill."""

from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

import pytest
from wear_support import GARMIN_USER, fixture, form_of, link_row, make_link, records, request

API = r"https://apis\.garmin\.com"
QS = {"provider": "garmin"}
PERSON = "00000000-0000-4000-8000-0000000000a1"


def test_the_authorize_url_carries_pkce(adapter, org):
    url = adapter.begin_authorisation(
        org.ctx("garmin"), {"state": "st", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output["authorize_url"]
    q = parse_qs(urlsplit(url).query)
    assert (
        url.startswith("https://connect.garmin.com/oauth2Confirm?")
        and q["code_challenge"] == ["C" * 43]
        and q["code_challenge_method"] == ["S256"]
    )
    assert q["client_id"] == ["platform-garmin-id"] and q["response_type"] == ["code"]


def test_completion_exchanges_the_code_with_the_verifier_and_asks_garmin_who_the_user_is(adapter, transport, org):
    transport.on("POST", r"connectapi\.garmin\.com/di-oauth2-service/oauth/token", "garmin/token.json")
    transport.on("GET", API + r"/wellness-api/rest/user/id", "garmin/user_id.json")
    r = adapter.complete_authorisation(
        org.ctx("garmin", secrets={}),
        {"code": "c1", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    )
    assert (
        r.error is None
        and r.output["provider_subject"] == GARMIN_USER
        and r.output["secrets"] == {"access_token": "garmin-access-1", "refresh_token": "garmin-refresh-1"}
    )
    assert r.output["granted_scopes"] == ["ACTIVITY_EXPORT", "HEALTH_EXPORT"]
    assert form_of(transport.last("POST", "oauth/token")) == {"client_id": "platform-garmin-id", "client_secret": "platform-garmin-secret", "grant_type": "authorization_code",
                                                              "code": "c1", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}  # fmt: skip
    assert transport.last("GET", "user/id").headers["authorization"] == "Bearer garmin-access-1"


def test_refresh_and_revoke(adapter, transport, org):
    transport.on("POST", r"oauth/token", "garmin/token.json")
    assert adapter.refresh_authorisation(org.ctx("garmin")).output["secrets"]["access_token"] == "garmin-access-1"
    assert form_of(transport.last("POST", "oauth/token"))["grant_type"] == "refresh_token"
    transport.on("DELETE", API + r"/wellness-api/rest/user/registration", status=204)
    assert adapter.revoke_authorisation(org.ctx("garmin")).output == {"revoked": True}


def push(adapter, name: str, ctx=None):
    r = adapter.verify_inbound(ctx, request(fixture(name), query=QS))
    assert r.error is None
    return r.output


def test_a_push_for_an_athlete_with_an_active_link_is_accepted_and_names_the_connection(adapter, org):
    make_link(org, "garmin")
    v = push(adapter, "garmin/push_health.json")
    assert v["verdict"] == "accept" and v["resolves_to"] == {
        "connection_id": org.connection_id,
        "account_link_subject": GARMIN_USER,
    }


@pytest.mark.parametrize("status", ["pending", "expired", "revoked"])
def test_a_push_for_anyone_else_is_rejected(adapter, org, status):
    assert push(adapter, "garmin/push_health.json")["verdict"] == "reject"  # nobody linked
    make_link(org, "garmin", status=status)
    assert push(adapter, "garmin/push_health.json")["verdict"] == "reject"


def test_a_push_is_stored_normalised_and_announced(adapter, org):
    ids = make_link(org, "garmin")
    out = adapter.parse_inbound(None, request(fixture("garmin/push_health.json"), query=QS)).output["notifications"]
    assert out == [{"port": "wearable-data", "kind": "data_available", "data": {"account_link_subject": GARMIN_USER,
                    "data_types": ["body_composition", "daily_summary", "heart_rate_variability", "sleep"], "from": "2026-11-03", "to": "2026-11-04"}}]  # fmt: skip
    by = {r.data_type: r.fields for r in records(ids["link"])}
    assert by["daily_summary"] == {"date": "2026-11-04", "steps": 12000, "distance_m": 9100.5, "active_kcal": 610.0, "resting_hr_bpm": 51, "avg_hr_bpm": 64, "max_hr_bpm": 172,
                                   "active_seconds": 4200, "stress_avg": 31, "source": "garmin"}  # fmt: skip
    assert (
        by["sleep"]["total_s"],
        by["sleep"]["deep_s"],
        by["sleep"]["light_s"],
        by["sleep"]["rem_s"],
        by["sleep"]["awake_s"],
        by["sleep"]["score"],
    ) == (27900, 5400, 14400, 6300, 1800, 82)
    assert by["heart_rate_variability"] == {"date": "2026-11-04", "rmssd_ms": 63.0, "source": "garmin"}
    assert by["body_composition"]["weight_kg"] == 71.45 and by["body_composition"]["body_fat_pct"] == 14.3
    assert link_row(ids["link"]).last_data_at is not None


def test_a_redelivered_push_changes_one_row_not_two(adapter, org):
    ids = make_link(org, "garmin")
    for _ in range(3):
        adapter.parse_inbound(None, request(fixture("garmin/push_health.json"), query=QS))
    assert len(records(ids["link"])) == 4


def test_pushed_activities(adapter, org):
    ids = make_link(org, "garmin")
    adapter.parse_inbound(None, request(fixture("garmin/push_activities.json"), query=QS))
    (rec,) = records(ids["link"])
    assert (
        rec.fields["sport"] == "running"
        and rec.fields["started_at"] == "2026-11-04T04:00:00+00:00"
        and rec.fields["duration_s"] == 2700
        and rec.fields["kcal"] == 540.0
    )


def test_corrupt_values_become_none_and_garbage_entries_are_skipped(adapter, org):
    ids = make_link(org, "garmin")
    r = adapter.parse_inbound(None, request(fixture("garmin/push_corrupt.json"), query=QS))
    assert r.error is None
    (rec,) = records(ids["link"])
    f = rec.fields
    assert (
        f["steps"] is None and f["distance_m"] is None and f["active_kcal"] is None and f["resting_hr_bpm"] is None
    )  # negative, "NaN", Infinity, true
    assert f["avg_hr_bpm"] is None and f["max_hr_bpm"] is None and f["active_seconds"] is None and f["stress_avg"] == 40
    assert json.dumps(f, allow_nan=False)  # nothing non-finite is ever stored


def test_a_push_does_not_move_a_revoked_links_data_back_in(adapter, org):
    ids = make_link(org, "garmin")
    adapter.parse_inbound(None, request(fixture("garmin/push_deregistration.json"), query=QS))
    assert link_row(ids["link"]).status == "revoked"
    adapter.parse_inbound(None, request(fixture("garmin/push_health.json"), query=QS))
    assert records(ids["link"]) == []


def test_deregistration_revokes_the_link_and_deletes_its_records(adapter, org):
    ids = make_link(org, "garmin")
    adapter.parse_inbound(None, request(fixture("garmin/push_health.json"), query=QS))
    assert records(ids["link"])
    out = adapter.parse_inbound(None, request(fixture("garmin/push_deregistration.json"), query=QS)).output[
        "notifications"
    ]
    assert out == [
        {"port": "wearable-data", "kind": "link_revoked_by_provider", "data": {"account_link_subject": GARMIN_USER}}
    ]
    assert link_row(ids["link"]).status == "revoked" and records(ids["link"]) == []


def test_a_permission_change_narrows_the_link(adapter, org):
    ids = make_link(org, "garmin")
    assert adapter.parse_inbound(None, request(fixture("garmin/push_permissions.json"), query=QS)).output == {
        "notifications": []
    }
    assert link_row(ids["link"]).data_types == ["activity"]
    assert (
        adapter.sync(
            org.ctx("garmin", ids["person"], ids["link"]), {"account_link_id": ids["link"], "data_types": ["sleep"]}
        ).error["code"]
        == "consent_required"
    )


def test_business_starter_has_no_pull_and_no_history(adapter, transport, org):
    ids = make_link(org, "garmin")
    r = adapter.sync(org.ctx("garmin", ids["person"], ids["link"]), {"account_link_id": ids["link"]})
    assert r.error is None and r.output["stored"] == 0 and not transport.requests  # data arrives by push
    assert (
        adapter.request_backfill(org.ctx("garmin", ids["person"], ids["link"]), {"account_link_id": ids["link"]}).error[
            "code"
        ]
        == "unsupported"
    )
    assert adapter.capabilities(org.ctx("garmin")).output["capabilities"]["backfill_days"] == 0


def test_business_enterprise_pulls_by_day_and_can_backfill(adapter, transport, org):
    ids = make_link(org, "garmin")
    ctx = org.ctx("garmin", ids["person"], ids["link"], settings={"garmin_tier": "enterprise"})
    assert adapter.capabilities(ctx).output["capabilities"]["backfill_days"] == 30
    transport.on("GET", API + r"/wellness-api/rest/dailies", "garmin/pull_dailies.json")
    r = adapter.sync(
        ctx, {"account_link_id": ids["link"], "data_types": ["daily_summary"], "from": "2026-11-04", "to": "2026-11-05"}
    )
    assert r.error is None and r.output["stored"] == 1  # the same summary id on both days is one row
    q = parse_qs(urlsplit(str(transport.sent("GET", "rest/dailies")[0].url)).query)
    assert q == {"uploadStartTimeInSeconds": ["1793750400"], "uploadEndTimeInSeconds": ["1793836799"]}
    transport.on("GET", API + r"/wellness-api/rest/backfill/", status=202)
    b = adapter.request_backfill(
        ctx, {"account_link_id": ids["link"], "data_types": ["daily_summary", "sleep"], "from": "2026-09-01"}
    )
    assert b.output == {"requested": True, "available_from": "2026-10-06"}  # 30 days is what the tier allows
    assert len(transport.sent("GET", "backfill/")) == 2


def test_a_repeated_backfill_request_is_not_an_error(adapter, transport, org):
    ids = make_link(org, "garmin")
    ctx = org.ctx("garmin", ids["person"], ids["link"], settings={"garmin_tier": "enterprise"})
    transport.on("GET", API + r"/wellness-api/rest/backfill/", status=409, body={"errorMessage": "duplicate"})
    assert (
        adapter.request_backfill(ctx, {"account_link_id": ids["link"], "data_types": ["sleep"]}).output["requested"]
        is True
    )


def test_completing_the_link_asks_for_history_only_on_enterprise_and_never_fails_because_of_it(adapter, transport, org):
    link = "44444444-4444-4444-8444-444444444444"
    transport.on("POST", r"oauth/token", "garmin/token.json")
    transport.on("GET", API + r"/wellness-api/rest/user/id", "garmin/user_id.json")
    transport.on("GET", API + r"/wellness-api/rest/backfill/", status=500)
    ctx = org.ctx("garmin", PERSON, link, secrets={}, settings={"garmin_tier": "enterprise"})
    assert (
        adapter.link_account(
            ctx,
            {
                "person_id": PERSON,
                "provider": "garmin",
                "account_link_id": link,
                "state": "s",
                "code_challenge": "C" * 43,
                "redirect_uri": "https://hub.example/cb",
            },
        ).error
        is None
    )
    assert (
        adapter.complete_authorisation(
            ctx, {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"}
        ).error
        is None
    )
    assert (
        link_row(link).status == "active"
        and link_row(link).provider_subject == GARMIN_USER
        and transport.sent("GET", "backfill/")
    )
