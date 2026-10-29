"""The router and contracts/openapi.yaml describe the same API: the same routes, the same public routes, and each
staff route guarded by exactly the permission its contract summary names."""

from __future__ import annotations

import re

import yaml
from conftest import CONTRACTS
from eos_admissions.api.router import router
from fastapi.routing import APIRoute

METHODS = {"get", "post", "put", "patch", "delete"}
SPEC = yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))
PERMISSIONS = yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))

CONTRACT_OPS = {
    (method.upper(), path): op
    for path, item in SPEC["paths"].items()
    for method, op in item.items()
    if method in METHODS
}
ROUTES = {(method, r.path): r for r in router.routes if isinstance(r, APIRoute) for method in r.methods}


def required_permission(route: APIRoute) -> str | None:
    stack = list(route.dependant.dependencies)
    while stack:
        dep = stack.pop()
        if getattr(dep.call, "permission", None):
            return dep.call.permission
        stack.extend(dep.dependencies)
    return None


def contract_permission(op: dict) -> str | None:
    match = re.search(r"Permission (admissions:[\w-]+:[\w-]+)", " ".join(op.get("summary", "").split()))
    return match.group(1) if match else None


def test_router_and_contract_have_the_same_routes():
    assert set(ROUTES) == set(CONTRACT_OPS)
    assert len(ROUTES) == 16


def test_public_routes_are_exactly_the_contracts_anonymous_ones():
    public = {key for key, op in CONTRACT_OPS.items() if op.get("security") == []}
    assert len(public) == 5
    assert all(path.startswith("/public/{org_slug}/") for _, path in public)
    assert {key for key in ROUTES if key[1].startswith("/public/")} == public
    for key in public:
        assert required_permission(ROUTES[key]) is None, key


def test_each_staff_route_needs_the_permission_its_contract_names():
    for key, op in CONTRACT_OPS.items():
        if op.get("security") == []:
            continue
        expected = contract_permission(op)
        assert expected, f"{key} names no permission in its contract summary"
        assert required_permission(ROUTES[key]) == expected, key


def test_every_declared_permission_guards_a_route():
    declared = {p["key"] for p in PERMISSIONS["permissions"]}
    used = {required_permission(r) for r in ROUTES.values()} - {None}
    assert used == declared
