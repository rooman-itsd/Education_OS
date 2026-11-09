"""GET /alerts, the data behind the dashboard widget wearables.alerts on the coach's layout: who may call it, which
problems it reports, that it never shows a reading, and that it shows nothing of Strava beyond "linked"."""

from __future__ import annotations

import json
import re
import uuid
from datetime import timedelta

import pytest
from eos_core.config import load_role_grants, permissions_for
from eos_wearables.api.router import READ, router
from fastapi.routing import APIRoute
from wear_support import NOW, PREFIX, make_link

DAY = timedelta(days=1)


def get(client, org, role="coach", **params):
    return client.get(f"{PREFIX}/alerts", params=params, headers=getattr(org, role))


def kinds(r) -> list[tuple[str, str]]:
    return [(a["kind"], a["provider"]) for a in r.json()["items"]]


def test_the_coach_and_the_org_admin_hold_the_key_and_nobody_else_does():
    assert READ == "wearables:alert:read"
    assert READ in permissions_for(["coach"]) and READ in permissions_for(["org-admin"])
    assert READ not in permissions_for(["faculty"]) and READ not in permissions_for(["athlete"])
    assert {role for role, keys in load_role_grants().items() if READ in keys} == {"coach", "org-admin"}


def test_the_widget_the_coach_layout_names_is_backed_by_this_key():
    """platform/identity/config/dashboards/coach.yaml lists wearables.alerts; a layout whose widget no held key backs shows nothing."""
    import yaml

    root = __import__("pathlib").Path(__import__("os").environ["EOS_REPO_ROOT"])
    layout = yaml.safe_load((root / "platform/identity/config/dashboards/coach.yaml").read_text())
    assert "wearables.alerts" in layout["widgets"] and READ in permissions_for(["coach"])


def test_every_route_needs_a_token_and_the_permission(client, org):
    assert client.get(f"{PREFIX}/alerts").status_code == 401
    assert client.get(f"{PREFIX}/alerts", headers={"Authorization": "Bearer junk"}).status_code == 401
    for role in ("faculty", "athlete_token"):
        r = get(client, org, role)
        assert r.status_code == 403 and r.json()["code"] == "forbidden"
    assert get(client, org, "admin").status_code == 200


def test_every_route_names_its_permission_for_the_hosts_coverage_check():
    for route in router.routes:
        assert isinstance(route, APIRoute)
        assert {getattr(d.call, "permission", None) for d in route.dependant.dependencies} - {None} == {READ}


def test_a_user_without_an_organisation_gets_403(client):
    from eos_core.security import create_token

    token = create_token(user_id=str(uuid.uuid4()), organisation_id=None, roles=["coach"])
    assert client.get(f"{PREFIX}/alerts", headers={"Authorization": f"Bearer {token}"}).status_code == 403


def test_a_healthy_athlete_raises_no_alert(client, org):
    make_link(org, "polar", last_data_at=NOW - timedelta(hours=5), last_synced_at=NOW)
    assert get(client, org).json() == {"items": [], "next_cursor": None}


def test_expired_and_revoked_links(client, org):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    make_link(org, "polar", a, status="expired", status_since=NOW - 2 * DAY)
    make_link(org, "garmin", b, status="revoked", status_since=NOW - 3 * DAY)
    items = get(client, org).json()["items"]
    assert [(i["person_id"], i["kind"], i["provider"], i["since"]) for i in items] == [
        (b, "link_revoked", "garmin", "2026-11-02T06:00:00+00:00"), (a, "link_expired", "polar", "2026-11-03T06:00:00+00:00")]  # fmt: skip
    assert set(items[0]) == {"person_id", "provider", "kind", "since", "last_synced_at"}


def test_a_sync_that_keeps_failing_alerts_from_the_start_of_the_streak(client, org):
    a = str(uuid.uuid4())
    make_link(
        org, "polar", a, consecutive_failures=3, failing_since=NOW - DAY, last_data_at=NOW, last_synced_at=NOW - DAY
    )
    make_link(
        org, "garmin", consecutive_failures=2, failing_since=NOW - DAY, last_data_at=NOW
    )  # below the threshold of 3
    items = get(client, org).json()["items"]
    assert [(i["person_id"], i["kind"], i["since"]) for i in items] == [
        (a, "sync_failing", "2026-11-04T06:00:00+00:00")
    ]


def test_no_data_for_the_stale_period(client, org, monkeypatch):
    a, b = str(uuid.uuid4()), str(uuid.uuid4())
    make_link(org, "polar", a, last_data_at=NOW - 4 * DAY, last_synced_at=NOW - DAY)  # stale after 3 days
    make_link(org, "polar", b, last_data_at=NOW - 2 * DAY)
    items = get(client, org).json()["items"]
    assert [(i["person_id"], i["kind"], i["since"]) for i in items] == [
        (a, "no_recent_data", "2026-11-04T06:00:00+00:00")
    ]
    monkeypatch.setenv("WEARABLES_STALE_AFTER_DAYS", "1")
    assert {i["person_id"] for i in get(client, org).json()["items"]} == {a, b}


def test_a_link_that_never_sent_anything_counts_from_when_it_became_active(client, org):
    make_link(org, "polar", status_since=NOW - 5 * DAY, created_at=NOW - 5 * DAY)
    assert kinds(get(client, org)) == [("no_recent_data", "polar")]


def test_pending_links_are_not_a_problem_yet(client, org):
    make_link(org, "polar", status="pending")
    assert get(client, org).json()["items"] == []


def test_strava_shows_nothing_beyond_linked(client, org):
    s = str(uuid.uuid4())
    make_link(
        org, "strava", s, last_data_at=NOW - 30 * DAY, last_synced_at=NOW - 10 * DAY
    )  # silent for a month: that is Strava data, not shown
    assert get(client, org).json()["items"] == []
    make_link(org, "strava", s, status="expired", status_since=NOW - DAY, last_synced_at=NOW - 2 * DAY)
    (alert,) = get(client, org).json()["items"]
    assert alert["kind"] == "link_expired" and alert["provider"] == "strava" and alert["last_synced_at"] is None


def test_a_coach_asks_about_their_squad_and_learns_who_has_no_link(client, org):
    linked, never, other = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
    make_link(org, "polar", linked, status="expired", status_since=NOW - DAY)
    make_link(org, "polar", other, status="expired", status_since=NOW - DAY)  # not in the squad
    r = get(client, org, person_id=f"{linked},{never}")
    assert [(i["person_id"], i["kind"]) for i in r.json()["items"]] == [(linked, "link_expired"), (never, "not_linked")]
    assert next(i for i in r.json()["items"] if i["kind"] == "not_linked")["provider"] is None
    assert get(client, org, person_id=never, kind="link_expired").json()["items"] == []


def test_kind_filter_and_the_unfiltered_view_does_not_invent_not_linked(client, org):
    make_link(org, "polar", status="expired", status_since=NOW - DAY)
    make_link(org, "garmin", status="revoked", status_since=NOW - DAY)
    assert kinds(get(client, org, kind="link_revoked")) == [("link_revoked", "garmin")]
    assert all(k != "not_linked" for k, _ in kinds(get(client, org)))


def test_pages_follow_the_cursor_without_gaps_or_repeats(client, org):
    people = [str(uuid.uuid4()) for _ in range(5)]
    for i, p in enumerate(people):
        make_link(org, "polar", p, status="expired", status_since=NOW - timedelta(hours=i + 1))
    seen, cursor = [], None
    for _ in range(6):
        r = get(client, org, limit=2, **({"cursor": cursor} if cursor else {})).json()
        seen += [i["person_id"] for i in r["items"]]
        cursor = r["next_cursor"]
        if not cursor:
            break
    assert seen == people[::-1] and len(set(seen)) == 5


def test_an_organisation_sees_only_its_own_athletes(client, org, other_org):
    mine, theirs = str(uuid.uuid4()), str(uuid.uuid4())
    make_link(org, "polar", mine, status="expired", status_since=NOW - DAY)
    make_link(other_org, "polar", theirs, status="expired", status_since=NOW - DAY)
    assert [i["person_id"] for i in get(client, org).json()["items"]] == [mine]
    assert [i["person_id"] for i in get(client, other_org).json()["items"]] == [theirs]
    assert [i["kind"] for i in get(client, org, person_id=theirs).json()["items"]] == [
        "not_linked"
    ]  # their athlete is not ours


def test_the_response_never_carries_a_reading(client, org, adapter, transport):
    ids = make_link(org, "polar", status="active")
    transport.on("GET", r"polaraccesslink\.com/v3/exercises", "polar/exercises.json")
    adapter.sync(
        org.ctx("polar", ids["person"], ids["link"]),
        {"account_link_id": ids["link"], "data_types": ["activity"], "from": "2026-11-03", "to": "2026-11-05"},
    )
    make_link(org, "garmin", status="expired", status_since=NOW - DAY)
    body = json.dumps(get(client, org).json())
    uid = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
    body = re.sub(uid, "<id>", body)  # a random id can hold "152"
    for reading in ("8500", "152", "heart", "steps", "kcal", "weight", "sleep", "aQlC83"):
        assert reading not in body


@pytest.mark.parametrize("params", [{"limit": 0}, {"limit": 201}, {"limit": "x"}, {"kind": "everything"}, {"person_id": "not-a-uuid"}, {"person_id": ",".join(str(uuid.uuid4()) for _ in range(201))},
                                    {"cursor": "A" * 301}, {"person_id": "A" * 8001}])  # fmt: skip
def test_bad_parameters_are_4xx_never_500(client, org, params):
    assert get(client, org, **params).status_code in (400, 422)


@pytest.mark.parametrize("cursor", ["garbage", "!!!", "QQ==", "bm9wZQ=="])
def test_a_bad_cursor_is_400_invalid_cursor(client, org, cursor):
    r = get(client, org, cursor=cursor)
    assert r.status_code == 400 and r.json() == {"code": "invalid_request", "detail": "invalid_cursor"}


def test_two_hundred_person_ids_are_accepted_and_blank_entries_ignored(client, org):
    ids = [str(uuid.uuid4()) for _ in range(200)]
    r = get(client, org, person_id=",".join(ids) + ",")
    assert (
        r.status_code == 200 and len(r.json()["items"]) == 50 and r.json()["next_cursor"]
    )  # all 200 are not linked: a first page of 50
    assert get(client, org, person_id=",").json() == {"items": [], "next_cursor": None}
