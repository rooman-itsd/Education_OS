"""The router and contracts/ agree: the same operations, each guarded by the permission its x-permission names, every
role granting only catalogue keys, and every event published is declared in events.yaml with the same fields."""

from pathlib import Path

import pytest
import yaml
from conftest import BASE, outbox
from eos_core.db import new_id
from eos_skill_progress.api.router import router
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
# Keys the catalogue declares with no operation yet (docs/prd.md section 9, Q3: no export operation).
NO_OPERATION_YET = {"skill-progress:progress:export"}


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
    assert {op["x-permission"] for op in OPERATIONS.values()} == keys - NO_OPERATION_YET
    for role in PERMISSIONS["roles"]:
        assert set(role["grants"]) <= keys, role["name"]


def test_published_events_match_events_yaml(client, org):
    f, s, r = org.setup()
    learner = new_id()
    org.assess(learner, s, r, 50, "Developing", assessed_at="2026-10-01T10:00:00Z")
    org.assess(learner, s, r, 95, "Expert")
    declared = {e["name"]: set(e["payload"]) for e in EVENTS["events"]}
    published = {}
    for e in outbox(org.id):
        published.setdefault(e.name, set(e.payload))
        assert set(e.payload) == published[e.name], e.name  # every instance of an event has the same fields
    assert published == declared
    assert client.get(f"{BASE}/frameworks/{f['id']}", headers=org.admin).status_code == 200
