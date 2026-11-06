"""sync: idempotent upserts on (link, type, provider record id), freshness and failure bookkeeping, the date window, and
what a refused token or a refused data type does to the link."""

from __future__ import annotations

import json
import uuid
from datetime import date, timedelta

import httpx
import pytest
from wear_support import audit_actions, fixture_json, link_row, make_link, records

API = r"https://www\.strava\.com/api/v3/athlete/activities"
P = r"https://www\.polaraccesslink\.com/v3"


def strava_sync(adapter, org, ids, **over):
    return adapter.sync(
        org.ctx("strava", ids["person"], ids["link"]),
        {"account_link_id": ids["link"], "from": "2026-11-03", "to": "2026-11-05", **over},
    )


def test_a_redelivery_stores_nothing_new_and_a_correction_changes_one_row(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API, "strava/activities.json")
    assert strava_sync(adapter, org, ids).output["stored"] == 2
    again = strava_sync(adapter, org, ids).output
    assert (again["stored"], again["updated"]) == (0, 0) and len(records(ids["link"])) == 2
    fixed = fixture_json("strava/activities.json")
    fixed[0]["distance_m"] = 0
    fixed[0]["distance"] = 8200.0
    transport.routes.clear()
    transport.on("GET", API, body=fixed)
    out = strava_sync(adapter, org, ids).output
    assert (out["stored"], out["updated"]) == (0, 1)
    assert sorted(r.fields["distance_m"] for r in records(ids["link"])) == [8200.0, 25000.0]


def test_a_successful_sync_updates_freshness_and_clears_failures(adapter, transport, org, clock):
    ids = make_link(org, "strava", consecutive_failures=2, failing_since=clock.now, last_error_code="provider_error")
    transport.on("GET", API, "strava/activities.json")
    strava_sync(adapter, org, ids)
    row = link_row(ids["link"])
    assert row.consecutive_failures == 0 and row.failing_since is None and row.last_error_code is None
    assert row.last_synced_at.replace(tzinfo=None) == clock.now.replace(tzinfo=None) and row.last_data_at is not None


def test_an_empty_sync_is_fresh_but_is_not_new_data(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API, body=[])
    strava_sync(adapter, org, ids)
    row = link_row(ids["link"])
    assert row.last_synced_at is not None and row.last_data_at is None


@pytest.mark.parametrize(
    ("status", "code"), [(500, "provider_error"), (502, "provider_error"), (400, "invalid_request"), (404, "not_found")]
)
def test_failures_are_counted_and_the_first_one_dates_the_streak(adapter, transport, org, clock, status, code):
    ids = make_link(org, "strava")
    transport.on("GET", API, status=status, body={})
    first = clock.now
    assert strava_sync(adapter, org, ids).error["code"] == code
    clock.advance(hours=1)
    strava_sync(adapter, org, ids)
    row = link_row(ids["link"])
    assert (
        row.consecutive_failures == 2
        and row.last_error_code == code
        and row.failing_since.replace(tzinfo=None) == first.replace(tzinfo=None)
        and row.status == "active"
    )


def test_a_network_failure_is_transport_unavailable_and_counts(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API, raises=httpx.ConnectTimeout("t"))
    e = strava_sync(adapter, org, ids).error
    assert (
        e["code"] == "transport_unavailable"
        and e["retryable"] is True
        and link_row(ids["link"]).consecutive_failures == 1
    )


def test_a_provider_that_answers_garbage_is_a_provider_error_not_a_crash(adapter, transport, org):
    ids = make_link(org, "strava")
    for body in ("not json", "null", '"x"', "5"):
        transport.routes.clear()
        transport.on("GET", API, status=200, body=body)
        assert strava_sync(adapter, org, ids).error["code"] == "provider_error"


def test_nan_and_infinity_from_a_provider_are_never_stored(adapter, transport, org):
    ids = make_link(org, "strava")
    raw = '[{"id": 1, "sport_type": "Run", "start_date": "2026-11-04T01:00:00Z", "moving_time": 10, "distance": NaN, "average_heartrate": Infinity, "max_heartrate": -Infinity, "suffer_score": 1e999}]'
    transport.on("GET", API, status=200, body=raw)
    assert strava_sync(adapter, org, ids).output["stored"] == 1
    f = records(ids["link"])[0].fields
    assert (
        f["distance_m"] is None and f["avg_hr_bpm"] is None and f["max_hr_bpm"] is None and f["training_load"] is None
    )
    assert json.dumps(f, allow_nan=False)


def test_a_link_that_is_not_active_cannot_sync(adapter, org):
    for status in ("pending", "expired", "revoked"):
        ids = make_link(org, "strava", status=status)
        e = strava_sync(adapter, org, ids).error
        assert e["code"] == "consent_required" and status in e["detail"]


def test_an_unknown_link_or_another_providers_link_is_not_found(adapter, org):
    assert adapter.sync(org.ctx("strava"), {"account_link_id": str(uuid.uuid4())}).error["code"] == "not_found"
    ids = make_link(org, "polar")
    assert adapter.sync(org.ctx("strava"), {"account_link_id": ids["link"]}).error["code"] == "not_found"


def test_a_type_the_link_does_not_cover_is_consent_required(adapter, org):
    ids = make_link(org, "polar", types=["activity"])
    e = adapter.sync(
        org.ctx("polar", ids["person"], ids["link"]), {"account_link_id": ids["link"], "data_types": ["sleep"]}
    ).error
    assert e["code"] == "consent_required" and "sleep" in e["detail"]


def test_the_default_window_is_the_day_before_the_last_sync_or_the_default_backfill(adapter, transport, org, clock):
    ids = make_link(org, "strava")
    transport.on("GET", API, body=[])
    ctx = org.ctx("strava", ids["person"], ids["link"])
    first = adapter.sync(ctx, {"account_link_id": ids["link"]}).output
    assert first["from"] == "2026-10-06" and first["to"] == "2026-11-05"  # WEARABLES_DEFAULT_BACKFILL_DAYS = 30
    clock.advance(days=2)
    second = adapter.sync(ctx, {"account_link_id": ids["link"]}).output
    assert second["from"] == "2026-11-04" and second["to"] == "2026-11-07"


def test_a_window_is_clamped_to_the_pulls_own_pages(adapter, transport, org):
    ids = make_link(org, "strava")
    page = [{"id": i, "sport_type": "Run", "start_date": "2026-11-04T01:00:00Z", "moving_time": 10} for i in range(100)]
    transport.on("GET", API, status=200, body=page)
    assert strava_sync(adapter, org, ids).output["stored"] == 100
    assert (
        len(transport.sent("GET", "athlete/activities")) == 10
    )  # ten pages of 100 at most, however long the athlete's list


def test_stored_records_survive_a_provider_outage_and_the_audit_trail_has_no_readings(adapter, transport, org):
    ids = make_link(org, "strava")
    transport.on("GET", API, "strava/activities.json")
    strava_sync(adapter, org, ids)
    transport.routes.clear()
    transport.on("GET", API, status=503)
    strava_sync(adapter, org, ids)
    assert len(records(ids["link"])) == 2 and audit_actions(org) == ["records.stored"]


def test_only_the_organisation_enabled_types_are_collected(adapter, transport, org):
    ids = make_link(org, "polar")
    transport.on("GET", P + "/exercises", "polar/exercises.json")
    ctx = org.ctx("polar", ids["person"], ids["link"], settings={"data_types": ["activity"]})
    out = adapter.sync(ctx, {"account_link_id": ids["link"], "from": "2026-11-03", "to": "2026-11-05"}).output
    assert (
        out["stored"] == 1
        and not transport.sent("GET", "users/activities")
        and not transport.sent("GET", "users/sleep")
    )
    _ = date, timedelta
