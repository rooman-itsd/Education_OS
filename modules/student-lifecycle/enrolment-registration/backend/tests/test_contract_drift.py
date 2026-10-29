"""The router and contracts/openapi.yaml describe the same API: the same routes, and each guarded by exactly the
permission its `x-permission` names."""

from __future__ import annotations

import yaml
from conftest import CONTRACTS
from eos_enrolment_registration.api.router import router
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


def test_router_and_contract_have_the_same_routes():
    assert set(ROUTES) == set(CONTRACT_OPS)
    assert len(ROUTES) == 14


def test_each_route_needs_exactly_its_x_permission():
    for key, op in CONTRACT_OPS.items():
        assert required_permission(ROUTES[key]) == op["x-permission"], key


def test_every_declared_permission_guards_a_route():
    declared = {p["key"] for p in PERMISSIONS["permissions"]}
    assert {required_permission(r) for r in ROUTES.values()} == declared
