"""The router and contracts/ agree: the same operations, each guarded by the permission its x-permission names, every
permission key in permissions.yaml, and every event published is declared in events.yaml with the same fields."""

from pathlib import Path

import pytest
import yaml
from conftest import outbox
from eos_athlete_performance.api.router import router
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
    d = org.discipline()
    m = org.metric()
    a = org.athlete(
        d["id"], coach_id="44444444-4444-4444-4444-444444444444", user_id="55555555-5555-5555-5555-555555555555"
    )
    org.client.patch(f"/api/v1/athlete-performance/athletes/{a['id']}", json={"squad": "A"}, headers=org.admin)
    org.result(a["id"], m["id"], 12.0)
    t = org.post("/fitness-tests", {"name": "Speed", "metric_ids": [m["id"]]})
    org.post(
        "/assessments",
        {
            "athlete_id": a["id"],
            "fitness_test_id": t["id"],
            "assessed_on": "2026-10-28",
            "measurements": [{"metric_id": m["id"], "value": 12}],
        },
    )
    org.post("/benchmarks", {"metric_id": m["id"], "level": "state", "target_value": 12.5})
    org.client.put(
        f"/api/v1/athlete-performance/athletes/{a['id']}/clearance",
        json={"status": "cleared", "valid_until": "2026-12-31"},
        headers=org.admin,
    )
    declared = {e["name"]: set(e["payload"]) for e in EVENTS["events"]}
    published = {e.name: set(e.payload) for e in outbox(org.id)}
    assert published == declared
