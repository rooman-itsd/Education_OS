"""The router and contracts/ agree: the same operations, each guarded by the permission its x-permission names, every
permission key in permissions.yaml, and every event published is declared in events.yaml with the same fields."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
import yaml
from conftest import outbox
from eos_tournament_events.api.router import router
from fastapi.routing import APIRoute

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
OPENAPI = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
PERMISSIONS = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
EVENTS = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
METHODS = {"get", "put", "post", "patch", "delete"}
OPERATIONS = {
    (method.upper(), path): op
    for path, item in OPENAPI["paths"].items()
    for method, op in item.items()
    if method in METHODS
}


def _route_permissions() -> dict[tuple[str, str], str]:
    """(METHOD, path) -> the permission the route's `require` dependency checks."""
    out = {}
    for route in router.routes:
        assert isinstance(route, APIRoute)
        for method in route.methods:
            deps = [d.call for d in route.dependant.dependencies]
            perms = [
                c.__closure__[0].cell_contents for c in deps if getattr(c, "__name__", "") == "dep" and c.__closure__
            ]
            out[(method, route.path)] = perms[0] if perms else None
    return out


def test_routes_match_the_contract_operations():
    assert set(_route_permissions()) == set(OPERATIONS)


@pytest.mark.parametrize("key", sorted(OPERATIONS), ids=[f"{m} {p}" for m, p in sorted(OPERATIONS)])
def test_each_route_checks_the_contract_permission(key):
    assert _route_permissions()[key] == OPERATIONS[key]["x-permission"]
    assert OPERATIONS[key]["responses"].get("403") == {"$ref": "#/components/responses/Forbidden"}


def test_every_x_permission_is_in_the_catalogue_and_every_role_grants_known_keys():
    keys = {p["key"] for p in PERMISSIONS["permissions"]}
    assert {op["x-permission"] for op in OPERATIONS.values()} == keys
    for role in PERMISSIONS["roles"]:
        assert set(role["grants"]) <= keys, role["name"]


def test_published_events_match_events_yaml(client, org):
    t = org.tournament(registration_closes_on="2026-11-05")
    e = org.entry(t["id"], ["11111111-1111-1111-1111-111111111111"])
    f = org.fixture(t["id"], [e["id"]], at="2026-11-10T04:30:00Z")
    org.post(
        f"/tournaments/{t['id']}/officials", {"name": "R. Iyer", "official_role": "referee", "fixture_id": f["id"]}
    )
    declared = {ev["name"]: set(ev["payload"]) for ev in EVENTS["events"]}
    published = {ev.name: set(ev.payload) for ev in outbox(org.id)}
    # result.recorded needs the fixture to have started and cancelling ends the tournament: the next test
    assert published == {k: v for k, v in declared.items() if not k.endswith(("result.recorded", "cancelled"))}


def test_result_and_cancel_events_match_events_yaml(client, org, later):
    t = org.tournament(registration_closes_on="2026-11-05")
    e = org.entry(t["id"], ["11111111-1111-1111-1111-111111111111"])
    f = org.fixture(t["id"], [e["id"]], at="2026-11-10T04:30:00Z")
    later(datetime(2026, 11, 10, 6, 0, tzinfo=UTC))
    r = org.client.put(
        f"/api/v1/tournament-events/tournaments/{t['id']}/fixtures/{f['id']}/result",
        json={"placings": [{"entry_id": e["id"], "position": 1, "mark": 10.9, "unit": "s"}]},
        headers=org.admin,
    )
    assert r.status_code == 200, r.text
    org.post(f"/tournaments/{t['id']}/cancel", {"reason": "Rain"}, status=200)
    declared = {ev["name"]: ev["payload"] for ev in EVENTS["events"]}
    [recorded] = outbox(org.id, "tournament-events.result.recorded")
    assert set(recorded.payload) == set(declared["tournament-events.result.recorded"])
    assert set(recorded.payload["placings"][0]) == set(declared["tournament-events.result.recorded"]["placings"][0])
    [cancelled] = outbox(org.id, "tournament-events.tournament.cancelled")
    assert set(cancelled.payload) == set(declared["tournament-events.tournament.cancelled"])
