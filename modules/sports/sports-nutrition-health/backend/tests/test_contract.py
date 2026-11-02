"""The router and contracts/ agree: the same operations, each guarded by the permission its x-permission names, every
permission key in permissions.yaml, every event published declared in events.yaml with the same fields, and the
consumed event listed in module.yaml."""

from pathlib import Path

import pytest
import yaml
from conftest import outbox
from eos_core.db import new_id
from eos_sports_nutrition_health.api.router import router
from eos_sports_nutrition_health.application.consumers import CONSUMERS
from fastapi.routing import APIRoute

MODULE_DIR = Path(__file__).resolve().parents[2]
CONTRACTS = MODULE_DIR / "contracts"
OPENAPI = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
PERMISSIONS = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
EVENTS = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
MANIFEST = yaml.safe_load((MODULE_DIR / "module.yaml").read_text(encoding="utf-8"))
METHODS = {"get", "put", "post", "patch", "delete"}
OPERATIONS = {
    (method.upper(), path): op
    for path, item in OPENAPI["paths"].items()
    for method, op in item.items()
    if method in METHODS
}
ATHLETE_A = "11111111-1111-1111-1111-111111111111"


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
    health = {"sports-nutrition-health:health-record:read", "sports-nutrition-health:health-record:write"}
    with_health = {r["name"] for r in PERMISSIONS["roles"] if health & set(r["grants"])}
    assert with_health == {"sports-nutrition-health-admin", "sports-nutrition-health-medical", "medical-staff"}


def test_consumed_events_are_declared_in_the_manifest():
    assert set(CONSUMERS) == set(MANIFEST["consumes_events"])


def test_published_events_match_events_yaml(client, org):
    p = org.plan(ATHLETE_A)
    org.post(
        f"/nutrition-plans/{p['id']}/reviews",
        {"reviewed_on": "2026-10-28", "outcome": "continue", "next_review_on": "2026-11-10"},
    )
    i = org.injury(ATHLETE_A, expected_return_on="2026-11-20")
    org.client.patch(
        f"/api/v1/sports-nutrition-health/injuries/{i['id']}", json={"status": "resolved"}, headers=org.admin
    )
    org.appointment(ATHLETE_A, new_id())
    org.appointment(ATHLETE_A, new_id(), scheduled_at="2026-10-28T10:00:00Z", status="completed")
    declared = {e["name"]: set(e["payload"]) for e in EVENTS["events"]}
    published = {e.name: set(e.payload) for e in outbox(org.id)}
    assert published == declared
