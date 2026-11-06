"""read: stored records only, never the provider; a stated purpose, logged; Strava data only to its own athlete."""

from __future__ import annotations

import uuid

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_wearables.infrastructure.models import ReadLog
from sqlalchemy import select
from wear_support import make_link, records

API = r"https://www\.strava\.com/api/v3/athlete/activities"
P = r"https://www\.polaraccesslink\.com/v3"
PERSON = "00000000-0000-4000-8000-0000000000a1"


@pytest.fixture
def athlete(adapter, transport, org):
    """One athlete with a Polar link (exercise, daily summaries, sleep) and a Strava link (two activities)."""
    polar, strava = make_link(org, "polar", PERSON), make_link(org, "strava", PERSON)
    transport.on("GET", P + "/exercises", "polar/exercises.json")
    transport.on("GET", P + "/users/activities", "polar/activities.json")
    transport.on("GET", P + "/users/sleep", "polar/sleep.json")
    transport.on("GET", API, "strava/activities.json")
    adapter.sync(
        org.ctx("polar", PERSON, polar["link"]),
        {"account_link_id": polar["link"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    adapter.sync(
        org.ctx("strava", PERSON, strava["link"]),
        {"account_link_id": strava["link"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    return {"polar": polar, "strava": strava}


def read(adapter, org, purpose="coach_review", data_type="activity", **over):
    ctx = over.pop("ctx", None) or org.ctx("polar")
    return adapter.read(
        ctx,
        {
            "person_id": PERSON,
            "data_type": data_type,
            "from": "2026-11-01",
            "to": "2026-11-05",
            "purpose": purpose,
            **over,
        },
    )


def test_a_coach_reads_the_athletes_polar_data_but_not_their_strava_data(adapter, athlete, org):
    out = read(adapter, org).output
    assert [i["provider"] for i in out["items"]] == ["polar"] and out["items"][0]["provider_activity_id"] == "aQlC83"
    assert all(i["provider"] != "strava" for i in out["items"])


def test_the_athlete_sees_their_own_strava_data_as_well(adapter, athlete, org):
    out = read(adapter, org, "athlete_self", requester_person_id=PERSON).output
    assert sorted(i["provider"] for i in out["items"]) == ["polar", "strava", "strava"]
    via_link = read(
        adapter, org, "athlete_self", ctx=org.ctx("polar", PERSON, athlete["polar"]["link"])
    ).output  # the hub names the athlete in the context
    assert len(via_link["items"]) == 3


@pytest.mark.parametrize("asker", [None, "00000000-0000-4000-8000-0000000000b2"])
def test_athlete_self_must_really_be_the_athlete(adapter, athlete, org, asker):
    kw = {"requester_person_id": asker} if asker else {}
    e = read(adapter, org, "athlete_self", **kw).error
    assert e["code"] == "consent_required"


def test_every_coach_purpose_gets_the_same_strava_rule(adapter, athlete, org):
    for purpose in ("coach_review", "health_review", "squad_overview", "whatever_else"):
        assert [i["provider"] for i in read(adapter, org, purpose).output["items"]] == ["polar"]


def test_strava_is_shown_to_coaches_only_after_stravas_written_approval_is_set_on_the_connection(adapter, athlete, org):
    approved = org.ctx("polar", settings={"strava_shared_display_approved": True})
    # the records were stored while the approval was not in force, so they stay athlete-only: approval is not retroactive
    assert [i["provider"] for i in read(adapter, org, ctx=approved).output["items"]] == ["polar"]
    from eos_core.db import SessionLocal as S
    from eos_wearables.infrastructure.models import Record

    with platform_scope(), S() as db:  # stored under an approved connection: scope "all"
        for r in db.scalars(select(Record).where(Record.provider == "strava")):
            r.display_scope = "all"
        db.commit()
    assert sorted(i["provider"] for i in read(adapter, org, ctx=approved).output["items"]) == [
        "polar",
        "strava",
        "strava",
    ]
    # and withdrawing the approval hides them again at once, whatever was stored
    assert [i["provider"] for i in read(adapter, org).output["items"]] == ["polar"]
    assert [
        i["provider"]
        for i in read(adapter, org, ctx=org.ctx("polar", settings={"strava_shared_display_approved": "yes"})).output[
            "items"
        ]
    ] == ["polar"]


def test_records_stored_while_approved_are_shown_as_all_and_otherwise_athlete_only(adapter, transport, org):
    ids = make_link(org, "strava", PERSON)
    transport.on("GET", API, "strava/activities.json")
    adapter.sync(
        org.ctx("strava", PERSON, ids["link"], settings={"strava_shared_display_approved": True}),
        {"account_link_id": ids["link"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    assert {r.display_scope for r in records(ids["link"])} == {"all"}
    assert (
        len(
            read(adapter, org, ctx=org.ctx("strava", settings={"strava_shared_display_approved": True})).output["items"]
        )
        == 2
    )
    assert read(adapter, org, ctx=org.ctx("strava")).output["items"] == []


def test_capabilities_say_strava_may_not_be_shown_to_others(adapter, org):
    assert adapter.capabilities(org.ctx("strava")).output["capabilities"]["display_to_others_allowed"] is False
    assert all(
        adapter.capabilities(org.ctx(p)).output["capabilities"]["display_to_others_allowed"] is True
        for p in ("garmin", "polar", "google-health")
    )


def test_an_organisation_that_does_not_share_with_coaches_returns_nothing_to_them(adapter, athlete, org):
    ctx = org.ctx("polar", settings={"share_with_coaches": False})
    assert read(adapter, org, ctx=ctx).error["code"] == "consent_required"
    assert (
        len(read(adapter, org, "athlete_self", requester_person_id=PERSON, ctx=ctx).output["items"]) == 3
    )  # the athlete still sees their own


def test_no_device_link_means_no_data_and_a_revoked_link_means_none_either(adapter, org):
    assert read(adapter, org).error["code"] == "consent_required"
    make_link(org, "polar", PERSON, status="revoked")
    assert read(adapter, org).error["code"] == "consent_required"


def test_the_other_data_types(adapter, athlete, org):
    assert read(adapter, org, data_type="daily_summary").output["items"][0]["steps"] in (11234, 9000)
    sleep = read(adapter, org, data_type="sleep").output["items"]
    assert len(sleep) == 1 and sleep[0]["total_s"] == 26100
    assert read(adapter, org, data_type="heart_rate_variability").output["items"] == []


def test_dates_filter_and_order(adapter, athlete, org):
    days = [i["date"] for i in read(adapter, org, data_type="daily_summary").output["items"]]
    assert days == ["2026-11-03", "2026-11-04"]
    assert [
        i["date"] for i in read(adapter, org, data_type="daily_summary", **{"from": "2026-11-04"}).output["items"]
    ] == ["2026-11-04"]
    assert (
        read(adapter, org, data_type="daily_summary", **{"from": "2026-10-01", "to": "2026-10-31"}).output["items"]
        == []
    )


def test_pages_follow_the_cursor_without_gaps_or_repeats(adapter, athlete, org):
    seen, cursor = [], None
    for _ in range(5):
        out = read(
            adapter, org, "athlete_self", requester_person_id=PERSON, limit=1, **({"cursor": cursor} if cursor else {})
        ).output
        seen += [i["provider_activity_id"] for i in out["items"]]
        cursor = out["next_cursor"]
        if not cursor:
            break
    assert sorted(seen) == ["9876543210", "9876543211", "aQlC83"] and len(seen) == 3


def test_last_synced_at_is_the_freshest_link_the_reader_may_see(adapter, athlete, org, clock):
    out = read(adapter, org).output
    assert out["last_synced_at"] == "2026-11-05T06:00:00+00:00"
    assert read(adapter, org, ctx=org.ctx("polar")).output["last_synced_at"] is not None


def test_every_read_is_logged_with_its_purpose_and_no_reading(adapter, athlete, org):
    read(adapter, org, "coach_review", caller_module="athlete-performance")
    read(adapter, org, "athlete_self", requester_person_id=PERSON)
    with platform_scope(), SessionLocal() as db:
        rows = db.scalars(select(ReadLog).where(ReadLog.organisation_id == org.id).order_by(ReadLog.purpose)).all()
    assert [(r.purpose, r.caller_module, r.data_type, str(r.date_from), str(r.date_to)) for r in rows] == [
        ("athlete_self", None, "activity", "2026-11-01", "2026-11-05"), ("coach_review", "athlete-performance", "activity", "2026-11-01", "2026-11-05")]  # fmt: skip
    assert not any(hasattr(r, "fields") for r in rows)


def test_a_refused_read_is_not_logged_as_a_read(adapter, athlete, org):
    read(adapter, org, "athlete_self")
    with platform_scope(), SessionLocal() as db:
        assert db.scalars(select(ReadLog)).all() == []


def test_read_never_calls_the_provider(adapter, athlete, transport, org):
    before = len(transport.requests)
    read(adapter, org)
    read(adapter, org, data_type="sleep")
    assert len(transport.requests) == before


def test_another_organisations_athlete_is_invisible(adapter, athlete, org, other_org):
    assert read(adapter, other_org, ctx=other_org.ctx("polar")).error["code"] == "consent_required"
    make_link(other_org, "polar", PERSON)
    assert (
        read(adapter, other_org, ctx=other_org.ctx("polar")).output["items"] == []
    )  # their own link, none of our data


@pytest.mark.parametrize("bad", [{"cursor": "garbage"}, {"cursor": "A" * 300}, {"limit": 0}, {"limit": 501}, {"limit": True}, {"limit": 1.5}, {"purpose": "Has Space"}, {"purpose": "x"}, {"purpose": "a" * 41},
                                 {"data_type": "everything"}, {"from": "2026-11-05", "to": "2026-11-01"}, {"from": "1999-01-01"}, {"to": "2101-01-01"}, {"from": "2020-01-01", "to": "2026-11-05"},
                                 {"from": "not a date"}, {"person_id": "x"}, {"caller_module": "Bad Module"}, {"requester_person_id": "x"}])  # fmt: skip
def test_bad_read_input_is_invalid_request(adapter, athlete, org, bad):
    e = read(adapter, org, **bad).error
    assert e["code"] == "invalid_request" and "retry" not in e["detail"]


def test_a_missing_field_is_invalid_request(adapter, org):
    assert adapter.read(org.ctx("polar"), {"person_id": PERSON}).error["code"] == "invalid_request"
    assert (
        adapter.read(
            org.ctx("polar"),
            {"person_id": str(uuid.uuid4()), "data_type": "sleep", "from": "2026-11-01", "to": "2026-11-05"},
        ).error["code"]
        == "invalid_request"
    )  # no purpose
