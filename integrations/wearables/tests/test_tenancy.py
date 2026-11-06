"""No organisation sees, changes or learns of another's links, records or reads (module standard rule 11)."""

from __future__ import annotations

import uuid

import pytest
from wear_support import link_row, make_link, records

PERSON = "00000000-0000-4000-8000-0000000000a1"


@pytest.fixture
def two_orgs(adapter, transport, org, other_org):
    transport.on("GET", r"athlete/activities", "strava/activities.json")
    out = {}
    for name, o in (("a", org), ("b", other_org)):
        ids = make_link(o, "strava", PERSON)
        adapter.sync(
            o.ctx("strava", PERSON, ids["link"]),
            {"account_link_id": ids["link"], "from": "2026-11-03", "to": "2026-11-05"},
        )
        out[name] = ids
    return out


@pytest.mark.parametrize("op", ["sync", "unlink_account", "request_backfill"])
def test_another_organisations_link_is_not_found(adapter, two_orgs, other_org, op):
    ctx = other_org.ctx("strava")
    r = getattr(adapter, op)(ctx, {"account_link_id": two_orgs["a"]["link"]})
    assert r.error["code"] == "not_found"
    assert link_row(two_orgs["a"]["link"]).status == "active" and len(records(two_orgs["a"]["link"])) == 2


def test_the_same_athlete_in_two_organisations_has_two_unrelated_sets_of_records(
    adapter, transport, two_orgs, org, other_org
):
    assert len(records(org=org)) == 2 and len(records(org=other_org)) == 2
    transport.on("POST", r"oauth/deauthorize", status=200, body={})
    adapter.unlink_account(org.ctx("strava"), {"account_link_id": two_orgs["a"]["link"]})
    assert records(org=org) == [] and len(records(org=other_org)) == 2


def test_reads_and_link_status_are_scoped_to_the_callers_organisation(adapter, two_orgs, org, other_org):
    ask = {
        "person_id": PERSON,
        "data_type": "activity",
        "from": "2026-11-01",
        "to": "2026-11-05",
        "purpose": "athlete_self",
        "requester_person_id": PERSON,
    }
    assert len(adapter.read(org.ctx("strava"), ask).output["items"]) == 2
    stranger = adapter.read({**org.ctx("strava"), "organisation_id": str(uuid.uuid4())}, ask)
    assert stranger.error["code"] == "consent_required"
    assert [
        i["account_link_id"] for i in adapter.link_status(org.ctx("strava"), {"person_ids": [PERSON]}).output["items"]
    ] == [two_orgs["a"]["link"]]


def test_a_webhook_for_an_athlete_linked_in_two_organisations_never_writes_into_the_wrong_one(adapter, org, other_org):
    from wear_support import GARMIN_USER, fixture, request

    a = make_link(org, "garmin")
    b = make_link(other_org, "garmin")
    adapter.parse_inbound(None, request(fixture("garmin/push_health.json"), query={"provider": "garmin"}))
    stored = {len(records(a["link"])), len(records(b["link"]))}
    assert stored == {0, 4}  # exactly one organisation's link received it, and never a mixture
    assert all(
        r.organisation_id in (org.id, other_org.id) and r.account_link_id in (a["link"], b["link"]) for r in records()
    )
    _ = GARMIN_USER
