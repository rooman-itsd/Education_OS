"""Every platform route is guarded by a key from a contracts/permissions.yaml catalogue, or is on the
explicit public list below. Keys named in code must exist in a catalogue, and the role grants must
let an organisation member open the shell while keeping admin routes closed to them."""

import importlib
from pathlib import Path

import yaml
from eos_backend.main import PLATFORM_ROUTERS
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from fastapi.routing import APIRoute

ROOT = Path(__file__).resolve().parents[3]

# (method, path) pairs that are reachable without a catalogue key, each with the reason.
PUBLIC = {
    ("GET", "/api/v1/health"): "liveness",
    ("POST", "/api/v1/identity/auth/login"): "authentication itself",
    ("GET", "/api/v1/identity/auth/me"): "who am I: any active user, returns their own permissions",
    ("GET", "/api/v1/identity/auth/oidc/config"): "ADR-0006: realm endpoints for the sign-in page, no secret",
    ("POST", "/api/v1/identity/auth/oidc/callback"): "ADR-0006: authentication itself (code exchange)",
    ("GET", "/api/v1/tenancy/academy-types"): "shown on the sign-up page",
    ("POST", "/api/v1/tenancy/register"): "self-service registration",
    ("POST", "/api/v1/tenancy/register/verify"): "email verification token",
    ("GET", "/api/v1/billing/plans"): "published price list on the sign-up page",
    ("POST", "/api/v1/billing/webhooks/payment"): "signed by the payment adapter, not a user",
}


def _catalogue() -> tuple[set[str], dict[str, set[str]]]:
    keys: set[str] = set()
    roles: dict[str, set[str]] = {}
    for f in ROOT.glob("platform/*/contracts/permissions.yaml"):
        data = yaml.safe_load(f.read_text()) or {}
        keys |= {p["key"] for p in data.get("permissions") or []}
        for r in data.get("roles") or []:
            roles.setdefault(r["name"], set()).update(r.get("grants") or [])
    return keys, roles


def _platform_routes():
    """(method, full path, route) for every route of every platform router, as main.py mounts them."""
    for name, dotted in PLATFORM_ROUTERS.items():
        for route in importlib.import_module(dotted).router.routes:
            if isinstance(route, APIRoute):
                for method in route.methods:
                    yield method, f"/api/v1/{name}{route.path_format}", route


def _required_key(route: APIRoute) -> str | None:
    for dep in route.dependant.dependencies:
        key = getattr(dep.call, "permission", None)
        if key:
            return key
    return None


def test_every_platform_route_names_a_catalogue_key_or_is_listed_public(client):
    keys, roles = _catalogue()
    granted = {k for ks in roles.values() for k in ks}
    unguarded, unknown, ungranted, seen = [], [], [], 0
    for method, path, route in _platform_routes():
        seen += 1
        key = _required_key(route)
        if key is None:
            if (method, path) not in PUBLIC:
                unguarded.append(f"{method} {path}")
        else:
            if key not in keys:
                unknown.append(f"{method} {path} -> {key}")
            if key not in granted:
                ungranted.append(f"{method} {path} -> {key}")
    assert seen >= 20, "expected the platform routers to be found"
    assert not unguarded, f"routes without a catalogue key and not listed public: {unguarded}"
    assert not unknown, f"keys used in code but missing from every permissions.yaml: {unknown}"
    assert not ungranted, f"keys no role grants, so nobody can call these: {ungranted}"


def test_public_list_matches_real_routes(client):
    real = {(m, p) for m, p, _ in _platform_routes()} | {("GET", "/api/v1/health")}
    stale = set(PUBLIC) - real
    assert not stale, f"PUBLIC lists routes that no longer exist: {stale}"
    # and the paths computed above are the ones the app really serves
    served = {(m.upper(), p) for p, ops in client.app.openapi()["paths"].items() for m in ops}
    assert real <= served, f"routes not served by the app: {real - served}"


def test_member_opens_the_shell_but_not_admin_routes(client):
    a = register_and_login(client, slug="perm-member", academy_type="music-academy")
    admin = auth(a["token"])
    r = client.post(
        "/api/v1/identity/users",
        json={"email": "m1@perm.example.com", "name": "M", "password": "Passw0rd!x", "roles": ["student"]},
        headers=admin,
    )
    assert r.status_code == 201, r.text
    r = client.post(
        "/api/v1/identity/auth/login",
        json={"email": "m1@perm.example.com", "password": "Passw0rd!x", "organisation_slug": "perm-member"},
    )
    assert r.status_code == 200, r.text
    member = auth(r.json()["token"])
    me = client.get("/api/v1/identity/auth/me", headers=member).json()
    assert me["roles"] == ["student"] and "tenancy:organisation:read" in me["permissions"]
    assert client.get("/api/v1/tenancy/organisation", headers=member).status_code == 200
    assert client.get("/api/v1/tenancy/organisation/entitlement", headers=member).status_code == 200
    # organisation-level reads and writes stay with roles the catalogue grants them to
    for method, path in [
        ("GET", "/api/v1/identity/users"),
        ("GET", "/api/v1/billing/subscription"),
        ("GET", "/api/v1/tenancy/admin/organisations"),
    ]:
        assert client.request(method, path, headers=member).status_code == 403, path
    r = client.post(
        "/api/v1/identity/users",
        json={"email": "m2@perm.example.com", "name": "M2", "password": "Passw0rd!x", "roles": ["student"]},
        headers=member,
    )
    assert r.status_code == 403


def test_super_admin_has_no_organisation_routes(client):
    r = client.post(
        "/api/v1/identity/auth/login", json={"email": "root@platform.example.com", "password": "RootPassw0rd!"}
    )
    sa = auth(r.json()["token"])
    assert client.get("/api/v1/tenancy/organisation", headers=sa).status_code == 403
    assert client.get("/api/v1/identity/users", headers=sa).status_code == 403
