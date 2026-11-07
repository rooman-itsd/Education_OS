"""Linking and unlinking: only the athlete's own link, the data types it covers, minors, and deletion at once on revoke."""

from __future__ import annotations

import uuid

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_wearables.application.consumers import CONSUMERS, on_account_link_revoked
from wear_support import audit_actions, link_input, link_row, make_link, records

PERSON = "00000000-0000-4000-8000-0000000000a1"
CONNECT = "polarremote.com/v2/oauth2/token"


def test_link_account_returns_the_authorize_url_and_records_a_pending_link(adapter, org):
    r = adapter.link_account(org.ctx("strava"), link_input(PERSON, "strava"))
    assert (
        r.error is None
        and r.output["authorize_url"].startswith("https://www.strava.com/oauth/authorize?")
        and r.output["data_types"] == ["activity"]
    )
    row = link_row(r.output["account_link_id"])
    assert (
        row.status == "pending"
        and row.person_id == PERSON
        and row.provider == "strava"
        and row.data_types == ["activity"]
    )
    assert audit_actions(org) == ["link.started"]


def test_the_hubs_link_id_is_kept(adapter, org):
    link = str(uuid.uuid4())
    assert (
        adapter.link_account(org.ctx("polar"), link_input(PERSON, "polar", account_link_id=link)).output[
            "account_link_id"
        ]
        == link
    )


def test_the_types_are_what_was_asked_what_the_provider_offers_and_what_the_organisation_collects(adapter, org):
    ctx = org.ctx("polar", settings={"data_types": ["activity", "sleep", "heart_rate_variability"]})
    assert adapter.link_account(ctx, link_input(PERSON, "polar")).output["data_types"] == [
        "activity",
        "sleep",
    ]  # polar has no hrv
    assert adapter.link_account(ctx, link_input(PERSON, "polar", data_types=["sleep"])).output["data_types"] == [
        "sleep"
    ]
    for ask in (["body_composition"], ["heart_rate_variability"]):
        e = adapter.link_account(ctx, link_input(PERSON, "polar", data_types=ask)).error
        assert e["code"] == "invalid_request" and "none of the requested" in e["detail"]
    assert (
        adapter.link_account(org.ctx("strava", settings={"data_types": ["sleep"]}), link_input(PERSON, "strava")).error[
            "code"
        ]
        == "invalid_request"
    )


def test_a_second_active_link_to_the_same_provider_conflicts_but_another_provider_is_fine(adapter, org):
    make_link(org, "strava", PERSON)
    assert adapter.link_account(org.ctx("strava"), link_input(PERSON, "strava")).error["code"] == "conflict"
    assert adapter.link_account(org.ctx("polar"), link_input(PERSON, "polar")).error is None
    assert (
        adapter.link_account(org.ctx("strava"), link_input(str(uuid.uuid4()), "strava")).error is None
    )  # another athlete


def test_starting_again_before_finishing_reuses_the_pending_link_and_an_expired_link_can_be_remade(adapter, org):
    a = adapter.link_account(org.ctx("strava"), link_input(PERSON, "strava")).output["account_link_id"]
    assert adapter.link_account(org.ctx("strava"), link_input(PERSON, "strava")).output["account_link_id"] == a
    b = make_link(org, "polar", PERSON, status="expired")
    again = adapter.link_account(org.ctx("polar"), link_input(PERSON, "polar")).output["account_link_id"]
    assert again == b["link"] and link_row(again).status == "pending"


def test_a_minor_cannot_link_a_device_until_a_guardian_consent_is_recorded(adapter, org):
    e = adapter.link_account(org.ctx("strava"), link_input(PERSON, "strava", minor=True)).error
    assert e["code"] == "invalid_request" and "guardian_consent_required" in e["detail"]
    assert (
        adapter.link_account(
            org.ctx("strava"), link_input(PERSON, "strava", minor=True, guardian_consent_recorded=True)
        ).error
        is None
    )
    assert adapter.link_account(org.ctx("polar"), link_input(PERSON, "polar", minor=False)).error is None


def test_the_providers_of_the_call_and_of_the_input_must_agree(adapter, org):
    assert adapter.link_account(org.ctx("strava"), link_input(PERSON, "polar")).error["code"] == "invalid_request"
    assert adapter.link_account({**org.ctx("strava"), "provider": "nonesuch"}, link_input(PERSON, "nonesuch")).error[
        "code"
    ] in ("not_configured", "invalid_request")


def test_the_whole_flow_link_then_authorise_then_sync_then_read_for_polar(adapter, transport, org):
    link = str(uuid.uuid4())
    assert (
        adapter.link_account(org.ctx("polar", PERSON, link), link_input(PERSON, "polar", account_link_id=link)).error
        is None
    )
    transport.on("POST", CONNECT, "polar/token.json")
    transport.on("POST", r"polaraccesslink\.com/v3/users$", status=200, body={})
    done = adapter.complete_authorisation(
        org.ctx("polar", PERSON, link, secrets={}),
        {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
    )
    assert done.error is None and link_row(link).status == "active" and link_row(link).provider_subject == "475"
    transport.on("GET", r"polaraccesslink\.com/v3/exercises", "polar/exercises.json")
    assert (
        adapter.sync(
            org.ctx("polar", PERSON, link),
            {"account_link_id": link, "data_types": ["activity"], "from": "2026-11-03", "to": "2026-11-05"},
        ).output["stored"]
        == 1
    )
    got = adapter.read(
        org.ctx("polar"),
        {
            "person_id": PERSON,
            "data_type": "activity",
            "from": "2026-11-01",
            "to": "2026-11-05",
            "purpose": "coach_review",
        },
    ).output
    assert got["items"][0]["provider_activity_id"] == "aQlC83" and got["items"][0]["provider"] == "polar"
    assert sorted(audit_actions(org)) == [
        "link.connected",
        "link.started",
        "records.stored",
    ]  # one fixed test clock: no order among equals


def test_unlink_deletes_every_record_at_once_marks_the_link_revoked_and_revokes_at_the_provider(
    adapter, transport, org
):
    ids = make_link(org, "polar", PERSON)
    transport.on("GET", r"polaraccesslink\.com/v3/exercises", "polar/exercises.json")
    adapter.sync(
        org.ctx("polar", PERSON, ids["link"]),
        {"account_link_id": ids["link"], "data_types": ["activity"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    other = make_link(org, "strava", PERSON)
    transport.on("POST", r"strava\.com/api/v3|oauth/token", status=200, body={})
    assert len(records(ids["link"])) == 1
    transport.on("DELETE", r"polaraccesslink\.com/v3/users/475", status=204)
    r = adapter.unlink_account(
        org.ctx("polar", PERSON, ids["link"]), {"account_link_id": ids["link"], "reason": "athlete disconnected"}
    )
    assert r.output == {"account_link_id": ids["link"], "status": "revoked", "records_deleted": 1}
    assert (
        records(ids["link"]) == []
        and link_row(ids["link"]).status == "revoked"
        and transport.sent("DELETE", "users/475")
    )
    assert link_row(other["link"]).status == "active"  # another provider's link is untouched
    again = adapter.unlink_account(org.ctx("polar", PERSON, ids["link"]), {"account_link_id": ids["link"]})
    assert again.output["records_deleted"] == 0  # idempotent
    assert audit_actions(org).count("link.revoked") == 2


def test_the_data_is_gone_even_when_the_provider_is_down_and_the_hub_is_told_to_retry(adapter, transport, org):
    ids = make_link(org, "polar", PERSON)
    transport.on("GET", r"polaraccesslink\.com/v3/exercises", "polar/exercises.json")
    adapter.sync(
        org.ctx("polar", PERSON, ids["link"]),
        {"account_link_id": ids["link"], "data_types": ["activity"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    transport.on("DELETE", r"polaraccesslink\.com/v3/users/475", status=503)
    e = adapter.unlink_account(org.ctx("polar", PERSON, ids["link"]), {"account_link_id": ids["link"]}).error
    assert e["code"] == "provider_error" and e["retryable"] is True
    assert records(ids["link"]) == [] and link_row(ids["link"]).status == "revoked"


def test_a_dead_token_at_the_provider_does_not_stop_the_unlink(adapter, transport, org):
    ids = make_link(org, "polar", PERSON)
    transport.on("DELETE", r"polaraccesslink\.com/v3/users/475", status=401)
    assert adapter.unlink_account(org.ctx("polar", PERSON, ids["link"]), {"account_link_id": ids["link"]}).error is None


def test_unlinking_an_unknown_link_is_not_found(adapter, org):
    assert adapter.unlink_account(org.ctx("polar"), {"account_link_id": str(uuid.uuid4())}).error["code"] == "not_found"


def test_the_revoked_event_deletes_what_was_collected_and_nothing_else(org, other_org, adapter, transport):
    class Event:
        def __init__(self, organisation_id, **payload):
            self.organisation_id, self.payload = organisation_id, payload

    ids = make_link(org, "strava", PERSON)
    mine = make_link(org, "strava", str(uuid.uuid4()), subject="1")
    theirs = make_link(other_org, "strava", PERSON)
    transport.on("GET", r"/athlete/activities", "strava/activities.json")
    for who, o in ((ids, org), (mine, org), (theirs, other_org)):
        adapter.sync(
            o.ctx("strava", who["person"], who["link"]),
            {"account_link_id": who["link"], "from": "2026-11-03", "to": "2026-11-05"},
        )
    assert [len(records(x["link"])) for x in (ids, mine, theirs)] == [2, 2, 2]
    with SessionLocal() as db:
        on_account_link_revoked(
            db, Event(org.id, account_link_id=ids["link"], port="wearable-data", provider="strava", cause="athlete")
        )
        db.commit()
        on_account_link_revoked(
            db, Event(org.id, account_link_id=ids["link"], port="wearable-data")
        )  # at-least-once delivery
        on_account_link_revoked(
            db, Event(org.id, account_link_id=mine["link"], port="digilocker")
        )  # another port's link
        on_account_link_revoked(
            db, Event(other_org.id, account_link_id=mine["link"], port="wearable-data")
        )  # not that organisation's
        on_account_link_revoked(db, Event(org.id, account_link_id=str(uuid.uuid4()), port="wearable-data"))
        on_account_link_revoked(db, Event(None, port="wearable-data"))
        db.commit()
    assert [len(records(x["link"])) for x in (ids, mine, theirs)] == [0, 2, 2]
    assert link_row(ids["link"]).status == "revoked" and link_row(mine["link"]).status == "active"
    assert CONSUMERS == {"integration-hub.account-link.revoked": on_account_link_revoked}
    _ = platform_scope


def test_link_status_lists_links_for_a_set_of_athletes(adapter, org, other_org):
    a, b = make_link(org, "polar", PERSON), make_link(org, "strava", PERSON)
    make_link(org, "polar", str(uuid.uuid4()))
    make_link(other_org, "polar", PERSON)
    out = adapter.link_status(org.ctx("polar"), {"person_ids": [PERSON]}).output["items"]
    assert {(i["account_link_id"], i["provider"], i["status"]) for i in out} == {
        (a["link"], "polar", "active"),
        (b["link"], "strava", "active"),
    }
    assert all(
        set(i) == {"person_id", "account_link_id", "provider", "status", "last_synced_at", "data_types"} for i in out
    )
    assert (
        next(i for i in out if i["provider"] == "strava")["last_synced_at"] is None
    )  # nothing of Strava's beyond "linked"
    assert adapter.link_status(org.ctx("polar"), {"person_ids": []}).output == {"items": []}


def test_retention_deletes_old_records_only(adapter, transport, org, monkeypatch, clock):
    ids = make_link(org, "polar", PERSON)
    transport.on("GET", r"polaraccesslink\.com/v3/exercises", "polar/exercises.json")
    adapter.sync(
        org.ctx("polar", PERSON, ids["link"]),
        {"account_link_id": ids["link"], "data_types": ["activity"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    monkeypatch.setenv("WEARABLES_RETENTION_DAYS", "2")
    assert adapter.purge_expired(org.ctx("polar")).output == {
        "records_deleted": 0,
        "older_than": "2026-11-03",
    }  # 4 November is within two days
    clock.advance(days=3)
    r = adapter.purge_expired(org.ctx("polar"))
    assert r.output == {"records_deleted": 1, "older_than": "2026-11-06"} and records(ids["link"]) == []
    assert adapter.purge_expired(org.ctx("polar")).output["records_deleted"] == 0


@pytest.mark.parametrize("n", [1])
def test_complete_authorisation_for_a_link_the_hub_made_first_is_created_on_the_fly(adapter, transport, org, n):
    link = str(uuid.uuid4())
    transport.on("POST", r"oauth/token", "strava/token_exchange.json")
    assert (
        adapter.complete_authorisation(
            org.ctx("strava", PERSON, link, secrets={}),
            {"code": "c", "code_verifier": "V" * 43, "redirect_uri": "https://hub.example/cb"},
        ).error
        is None
    )
    row = link_row(link)
    assert (
        row.status == "active"
        and row.person_id == PERSON
        and row.data_types == ["activity"]
        and row.provider_subject == "12345678"
    )
