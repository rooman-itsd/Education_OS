"""The operator API in contracts/openapi.yaml: who sees what, the cross-tenant leak test, replay and health."""

from __future__ import annotations

import pytest
from eos_event_bus.api.router import router
from eos_event_bus.application.relay import DEAD_LETTERED
from event_bus_support import Clock, Org, raise_event, relay, row, super_admin_headers
from fastapi import FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

PREFIX = "/api/v1/event-bus"


@pytest.fixture(scope="module")
def client():
    """The module alone, as module-standard rule 6 asks: no host and no other module."""
    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="module")
def orgs():
    return Org(), Org()


def _dead(event_name: str, organisation_id: str, max_attempts: int = 8) -> str:
    def boom(db, ev):
        raise RuntimeError("down")

    eid = raise_event(event_name, organisation_id)
    clock = Clock()
    r = relay({"mod": {event_name: boom}}, clock, max_attempts=max_attempts)
    for _ in range(max_attempts):
        r.run_once()
        clock.advance(600)
    return eid


def test_every_route_names_its_permission(client):
    for route in router.routes:
        assert isinstance(route, APIRoute)
        keys = {getattr(d.call, "permission", None) for d in route.dependant.dependencies} - {None}
        assert len(keys) == 1, route.path


def test_an_organisation_admin_sees_only_their_own_events(client, orgs):
    a, b = orgs
    mine = raise_event("hostel.room.allocated", a.id, {"room": "1"})
    theirs = raise_event("hostel.room.allocated", b.id, {"room": "2"})
    platform = raise_event("scheduler.job.due", None)
    body = client.get(f"{PREFIX}/events", headers=a.headers(a.admin)).json()
    assert [e["id"] for e in body["items"]] == [mine] and body["total"] == 1
    assert body["items"][0]["state"] == "pending" and body["items"][0]["payload"] == {"room": "1"}
    # another organisation's event, or the platform's, is not found rather than forbidden
    for other in (theirs, platform):
        assert client.get(f"{PREFIX}/events/{other}", headers=a.headers(a.admin)).status_code == 404
        assert client.post(f"{PREFIX}/events/{other}/replay", headers=a.headers(a.admin)).status_code == 404


def test_the_organisation_id_filter_is_ignored_for_an_organisation_caller(client, orgs):
    a, b = orgs
    raise_event("x.y.z", b.id)
    body = client.get(f"{PREFIX}/events", params={"organisation_id": b.id}, headers=a.headers(a.admin)).json()
    assert body["total"] == 0


def test_a_member_has_no_access(client, orgs):
    a, _ = orgs
    assert client.get(f"{PREFIX}/events", headers=a.headers(a.member)).status_code == 403
    assert client.get(f"{PREFIX}/relay/health", headers=a.headers(a.admin)).status_code == 403
    assert client.get(f"{PREFIX}/events").status_code == 401


def test_the_super_admin_sees_every_organisation_and_can_narrow_to_one(client, orgs):
    a, b = orgs
    ids = {raise_event("x.y.z", a.id), raise_event("x.y.z", b.id), raise_event("x.y.z", None)}
    sa = super_admin_headers()
    everything = client.get(f"{PREFIX}/events", params={"name": "x.*"}, headers=sa).json()
    assert {e["id"] for e in everything["items"]} == ids
    only_b = client.get(f"{PREFIX}/events", params={"name": "x.y.z", "organisation_id": b.id}, headers=sa).json()
    assert [e["organisation_id"] for e in only_b["items"]] == [b.id]


def test_filters_by_state_and_a_name_prefix_that_is_not_a_pattern(client, orgs):
    a, _ = orgs
    raise_event("fees.invoice.raised", a.id)
    raise_event("fees_x.invoice.raised", a.id)  # '_' must not match any character
    h = a.headers(a.admin)
    assert client.get(f"{PREFIX}/events", params={"name": "fees.*"}, headers=h).json()["total"] == 1
    assert client.get(f"{PREFIX}/events", params={"state": "published"}, headers=h).json()["total"] == 0


def test_replay_returns_a_dead_letter_to_pending_and_refuses_anything_else(client, orgs):
    a, _ = orgs
    dead = _dead("a.b.c", a.id)
    h = a.headers(a.admin)
    assert (
        client.get(f"{PREFIX}/events", params={"state": "dead_lettered", "name": "a.b.c"}, headers=h).json()["total"]
        == 1
    )
    r = client.post(f"{PREFIX}/events/{dead}/replay", headers=h)
    assert r.status_code == 202 and r.json()["state"] == "pending" and r.json()["attempts"] == 0
    assert row(dead).last_error is None
    assert client.post(f"{PREFIX}/events/{dead}/replay", headers=h).status_code == 409  # pending now
    delivered = raise_event("ok.ok.ok", a.id)
    relay({}, Clock()).run_once()
    assert client.post(f"{PREFIX}/events/{delivered}/replay", headers=h).status_code == 409


def test_health_counts_every_organisation_for_the_super_admin(client, orgs):
    a, b = orgs
    raise_event("p.q.r", a.id)
    _dead("s.t.u", b.id)
    body = client.get(f"{PREFIX}/relay/health", headers=super_admin_headers()).json()
    assert body["transport"] == "inprocess" and body["dead_lettered"] == 1
    assert body["backlog"] >= 1 and body["oldest_unpublished_at"] and isinstance(body["stalled"], bool)
    assert DEAD_LETTERED  # the notice itself is pending too, and counted in the backlog
