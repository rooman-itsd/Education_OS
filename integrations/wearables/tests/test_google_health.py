"""Fitbit devices through the Google Health API. Its endpoints and shapes are assumptions (docs/prd.md, "Not verified"): these
tests pin the assumption, and its webhooks are refused until their verification is documented."""

from __future__ import annotations

import base64
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from eos_wearables.infrastructure.providers.google_health import _subject
from wear_support import fixture, form_of, make_link, records, request

H = r"https://health\.example/v1"


def test_the_authorize_url_is_googles_with_pkce_offline_access_and_our_scopes(adapter, org):
    url = adapter.begin_authorisation(
        org.ctx("google-health"), {"state": "st", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"}
    ).output["authorize_url"]
    q = parse_qs(urlsplit(url).query)
    assert (
        url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
        and q["code_challenge_method"] == ["S256"]
        and q["access_type"] == ["offline"]
    )
    assert q["scope"] == ["openid https://example.invalid/auth/health.read"] and q["prompt"] == ["consent"]


def test_without_scopes_or_a_client_nothing_is_authorised(adapter, org, monkeypatch):
    monkeypatch.delenv("WEARABLES_GOOGLE_HEALTH_SCOPES")
    assert (
        adapter.begin_authorisation(
            org.ctx("google-health"),
            {"state": "s", "code_challenge": "C" * 43, "redirect_uri": "https://hub.example/cb"},
        ).error["code"]
        == "not_configured"
    )


def test_completion_names_the_user_from_the_id_token_and_returns_both_tokens(adapter, transport, org):
    transport.on("POST", r"oauth2\.googleapis\.com/token", "google-health/token.json")
    r = adapter.complete_authorisation(
        org.ctx("google-health", secrets={}),
        {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    )
    assert r.error is None and r.output["provider_subject"] == "10987654321"
    assert (
        r.output["secrets"] == {"access_token": "google-access-1", "refresh_token": "google-refresh-1"}
        and r.output["expires_at"] == "2026-11-05T06:59:59+00:00"
    )
    assert form_of(transport.last("POST", "token"))["code_verifier"] == "V" * 43


@pytest.mark.parametrize(
    "token",
    [
        None,
        "",
        "a.b",
        "a.b.c.d",
        "x" * 9000,
        "a." + base64.urlsafe_b64encode(b"not json").decode() + ".c",
        "a." + base64.urlsafe_b64encode(b"[1]").decode() + ".c",
        5,
    ],
)
def test_a_bad_id_token_names_nobody(token):
    assert _subject(token) == ""


def test_refresh_keeps_the_refresh_token_google_did_not_resend_and_revoke_calls_google(adapter, transport, org):
    transport.on("POST", r"oauth2\.googleapis\.com/token", "google-health/token_refresh.json")
    out = adapter.refresh_authorisation(org.ctx("google-health")).output
    assert out["secrets"] == {"access_token": "google-access-2", "refresh_token": "google-refresh-1"}
    transport.on("POST", r"oauth2\.googleapis\.com/revoke", status=200, body={})
    assert adapter.revoke_authorisation(org.ctx("google-health")).output == {"revoked": True}
    assert form_of(transport.last("POST", "revoke")) == {"token": "google-refresh-1"}


def sync(adapter, org, ids, t):
    return adapter.sync(
        org.ctx("google-health", ids["person"], ids["link"]),
        {"account_link_id": ids["link"], "data_types": [t], "from": "2026-11-03", "to": "2026-11-05"},
    )


@pytest.mark.parametrize(("data_type", "path", "name"), [("daily_summary", "dailySummaries", "daily_summaries"), ("activity", "activities", "activities"), ("sleep", "sleep", "sleep"),
                                                         ("heart_rate_variability", "heartRateVariability", "hrv"), ("body_composition", "bodyComposition", "body")])  # fmt: skip
def test_every_data_type_is_pulled_and_normalised(adapter, transport, org, data_type, path, name):
    ids = make_link(org, "google-health")
    transport.on("GET", H + f"/users/me/{path}", f"google-health/{name}.json")
    assert sync(adapter, org, ids, data_type).output["stored"] == 1
    (rec,) = records(ids["link"])
    assert rec.data_type == data_type and rec.fields["source"] == "fitbit"
    q = parse_qs(urlsplit(str(transport.last("GET", path).url)).query)
    assert q == {"startDate": ["2026-11-03"], "endDate": ["2026-11-05"]}
    assert transport.last("GET", path).headers["authorization"] == "Bearer google-access-1"
    assert json.dumps(rec.fields, allow_nan=False)


def test_activity_fields(adapter, transport, org):
    ids = make_link(org, "google-health")
    transport.on("GET", H + "/users/me/activities", "google-health/activities.json")
    sync(adapter, org, ids, "activity")
    assert records(ids["link"])[0].fields == {"provider_activity_id": "ga1", "sport": "run", "started_at": "2026-11-04T06:00:00+00:00", "duration_s": 2500, "distance_m": 7200.0, "kcal": 480.0,
                                              "avg_hr_bpm": 150, "max_hr_bpm": 175, "training_load": 90.5, "hr_zones_s": [300, 900, 1000, 300], "source": "fitbit"}  # fmt: skip


def test_the_api_base_url_has_no_default(adapter, org, monkeypatch):
    ids = make_link(org, "google-health")
    monkeypatch.delenv("WEARABLES_GOOGLE_HEALTH_API_BASE_URL")
    assert sync(adapter, org, ids, "sleep").error["code"] == "not_configured"


def test_a_data_type_the_athlete_did_not_grant_is_consent_required_for_that_type_only(adapter, transport, org):
    ids = make_link(org, "google-health")
    transport.on("GET", H + "/users/me/sleep", status=403, body={"error": {"status": "PERMISSION_DENIED"}})
    transport.on("GET", H + "/users/me/activities", "google-health/activities.json")
    ctx = org.ctx("google-health", ids["person"], ids["link"])
    e = adapter.sync(ctx, {"account_link_id": ids["link"], "data_types": ["sleep"]}).error
    assert e["code"] == "consent_required" and e["provider_code"] == "403"
    r = adapter.sync(
        ctx,
        {"account_link_id": ids["link"], "data_types": ["sleep", "activity"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    assert (
        r.error is None and r.output["stored"] == 1
    )  # the granted type still synced, the refused one is dropped from the link
    from wear_support import link_row

    assert "sleep" not in link_row(ids["link"]).data_types and link_row(ids["link"]).status == "active"


def test_history_is_read_like_any_other_window(adapter, transport, org):
    ids = make_link(org, "google-health")
    transport.on("GET", H + "/users/me/activities", "google-health/activities.json")
    r = adapter.request_backfill(
        org.ctx("google-health", ids["person"], ids["link"]),
        {"account_link_id": ids["link"], "data_types": ["activity"], "from": "2026-09-01", "to": "2026-11-05"},
    )
    assert r.output == {
        "requested": True,
        "available_from": "2026-09-01",
    }  # within the 90 days the provider is asked for
    assert len(records(ids["link"])) == 1
    early = adapter.request_backfill(
        org.ctx("google-health", ids["person"], ids["link"]),
        {"account_link_id": ids["link"], "data_types": ["activity"], "from": "2025-01-01", "to": "2026-11-05"},
    )
    assert early.output["available_from"] == "2026-08-07"  # never further back than the capability says


def test_webhooks_are_not_accepted_until_google_documents_how_to_verify_them(adapter, org):
    make_link(org, "google-health")
    for headers in ({}, {"X-Goog-Signature": "abc"}, {"Authorization": "Bearer x"}):
        r = adapter.verify_inbound(
            None, request(fixture("google-health/activities.json"), headers, query={"provider": "google-health"})
        )
        assert r.output == {"verdict": "reject", "reject_status": 401}
    assert adapter.parse_inbound(None, request(b"{}", query={"provider": "google-health"})).output == {
        "notifications": []
    }
