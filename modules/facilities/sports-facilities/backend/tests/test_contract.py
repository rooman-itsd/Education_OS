"""The router and contracts/ agree: the same operations, each guarded by the permission its description names,
every permission key in permissions.yaml, the enums of the code are the contract's, and every event published is
declared in events.yaml with the same fields."""

import re
from pathlib import Path

import pytest
import yaml
from conftest import BASE, outbox
from eos_sports_facilities.application import service as svc
from eos_sports_facilities.domain import rules
from fastapi.routing import APIRoute

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
OPENAPI = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
PERMISSIONS = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))
EVENTS = yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))
SCHEMAS = OPENAPI["components"]["schemas"]
METHODS = {"get", "put", "post", "patch", "delete"}
OPERATIONS = {
    (method.upper(), path): op
    for path, item in OPENAPI["paths"].items()
    for method, op in item.items()
    if method in METHODS
}
PERMISSION_IN_TEXT = re.compile(r"Permission: `([^`]+)`")


def _contract_permission(op: dict) -> str:
    [key] = PERMISSION_IN_TEXT.findall(op["description"])
    return key


def _route_permissions() -> dict[tuple[str, str], str | None]:
    """(METHOD, path) -> the permission the route's `require` dependency checks."""
    from eos_sports_facilities.api.router import router

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
    assert _route_permissions()[key] == _contract_permission(OPERATIONS[key])
    assert OPERATIONS[key]["responses"].get("403") == {"$ref": "#/components/responses/Forbidden"}


def test_every_permission_is_in_the_catalogue_and_every_role_grants_known_keys():
    keys = {p["key"] for p in PERMISSIONS["permissions"]}
    assert {_contract_permission(op) for op in OPERATIONS.values()} == keys
    assert {svc.FACILITY_READ, svc.FACILITY_WRITE, svc.FACILITY_STATUS, svc.USAGE_READ, svc.USAGE_RECORD} == keys
    for role in PERMISSIONS["roles"]:
        assert set(role["grants"]) <= keys, role["name"]


def test_enums_are_the_contract_enums():
    assert list(rules.FACILITY_TYPES) == SCHEMAS["Facility"]["properties"]["facility_type"]["enum"]
    assert list(rules.STATUSES) == SCHEMAS["Facility"]["properties"]["status"]["enum"]
    assert list(rules.STATUSES) == SCHEMAS["SetStatusRequest"]["properties"]["status"]["enum"]
    assert list(rules.PURPOSES) == SCHEMAS["UsageRecord"]["properties"]["purpose"]["enum"]
    assert (
        list(rules.PURPOSES)
        == SCHEMAS["Utilisation"]["properties"]["by_purpose"]["items"]["properties"]["purpose"]["enum"]
    )


def _check_shape(body: dict, schema: str) -> None:
    spec = SCHEMAS[schema]
    assert set(spec["required"]) <= set(body), (schema, body)
    assert set(body) <= set(spec["properties"]), (schema, body)


def test_responses_have_the_contract_shapes_and_events_match_events_yaml(client, org):
    f = org.facility(capacity=40)
    _check_shape(f, "Facility")
    s = org.space(f["id"], capacity=10)
    _check_shape(s, "Space")
    org.client.patch(f"{BASE}/facilities/{f['id']}", json={"location": "South"}, headers=org.admin)
    st = org.client.put(
        f"{BASE}/facilities/{f['id']}/status",
        json={"status": "limited", "reason": "Rain", "until": "2026-11-01T00:00:00Z"},
        headers=org.admin,
    ).json()
    _check_shape(st, "Facility")
    u = org.usage(f["id"], "2026-10-26T06:00:00Z", "2026-10-26T07:00:00Z", space_id=s["id"], headcount=5)
    _check_shape(u, "UsageRecord")
    util = org.client.get(
        f"{BASE}/facilities/{f['id']}/utilisation?from=2026-10-26&to=2026-10-26", headers=org.admin
    ).json()
    _check_shape(util, "Utilisation")
    declared = {e["name"]: set(e["payload"]) for e in EVENTS["events"]}
    published = {e.name: set(e.payload) for e in outbox(org.id)}
    assert published == declared
