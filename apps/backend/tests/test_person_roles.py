"""No person may hold the `service` role, whichever way a role reaches them.

`service` is the catalogue holder of keys meant for no person (notification gives it notification:message:send;
modules send in-process, with no principal). A person holding it could send platform mail over HTTP to any
address. identity refuses it where every role assignment passes (application/service.create_user) and ignores it
again where every request's permissions are computed (api/deps.current_principal)."""

import uuid

from eos_core import config as core_config
from eos_core.db import SessionLocal
from eos_core.security import create_token, hash_password
from eos_core.tenant import organisation_scope
from eos_identity.domain.models import User
from eos_testing import register_and_login
from eos_testing.tenancy import auth

PROBE = "identity:user:manage"  # any real key will do: the test grants it to `service` and expects it ignored


def _new_user(roles: list[str]) -> dict:
    return {
        "email": f"p-{uuid.uuid4().hex[:8]}@roles.example.com",
        "name": "P",
        "password": "Passw0rd!x",
        "roles": roles,
    }


def _emails(client, admin) -> set[str]:
    return {u["email"] for u in client.get("/api/v1/identity/users", headers=admin).json()}


def test_an_organisation_admin_cannot_give_a_person_the_service_role(client):
    a = register_and_login(client, slug="roles-service")
    admin = auth(a["token"])
    for roles in (["service"], ["student", "service"]):
        body = _new_user(roles)
        r = client.post("/api/v1/identity/users", json=body, headers=admin)
        assert r.status_code == 403, r.text
        assert body["email"] not in _emails(client, admin)  # refused before anything was written


def test_a_caller_without_user_management_cannot_assign_any_role(client):
    a = register_and_login(client, slug="roles-member")
    admin = auth(a["token"])
    student = _new_user(["student"])
    assert client.post("/api/v1/identity/users", json=student, headers=admin).status_code == 201
    login = client.post(
        "/api/v1/identity/auth/login",
        json={"email": student["email"], "password": student["password"], "organisation_slug": "roles-member"},
    )
    member = auth(login.json()["token"])
    for roles in (["org-admin"], ["service"], ["student"]):
        assert client.post("/api/v1/identity/users", json=_new_user(roles), headers=member).status_code == 403


def test_ordinary_role_assignment_still_works(client):
    a = register_and_login(client, slug="roles-ordinary")
    admin = auth(a["token"])
    for roles in (["student"], ["faculty", "student"], ["org-admin"]):
        r = client.post("/api/v1/identity/users", json=_new_user(roles), headers=admin)
        assert r.status_code == 201 and r.json()["roles"] == roles, r.text


def test_platform_roles_stay_refused_inside_an_organisation(client):
    a = register_and_login(client, slug="roles-platform")
    r = client.post("/api/v1/identity/users", json=_new_user(["super-admin"]), headers=auth(a["token"]))
    assert r.status_code == 403


def test_registration_still_creates_the_organisation_admin(client):
    """Tenancy's registration is the other path through create_user; its fixed role is unaffected."""
    a = register_and_login(client, slug="roles-registration")
    me = client.get("/api/v1/identity/auth/me", headers=auth(a["token"])).json()
    assert me["roles"] == ["org-admin"] and "identity:user:manage" in me["permissions"]


def test_a_service_role_already_on_a_row_or_in_a_token_grants_nothing(client, monkeypatch):
    """The second guard: a row written before create_user refused it, or a token minted outside login. Both
    reach current_principal, where every principal is a person, and the role is dropped there. `service` is
    given a real key for this test, so the proof does not depend on which module grants it what."""
    real = core_config.load_role_grants()
    granted = {name: set(keys) for name, keys in real.items()}
    granted.setdefault("service", set()).add(PROBE)
    monkeypatch.setattr(core_config, "load_role_grants", lambda: granted)
    assert PROBE in core_config.permissions_for(["service"])  # the grant is live

    a = register_and_login(client, slug="roles-legacy")
    org = a["org"]["id"]
    with organisation_scope(org), SessionLocal() as db:
        row = User(
            organisation_id=org,
            email="legacy@roles.example.com",
            name="Legacy",
            password_hash=hash_password("Passw0rd!x"),
            roles=["student", "service"],
        )
        db.add(row)
        db.commit()
        user_id = row.id
    token = auth(create_token(user_id=user_id, organisation_id=org, roles=["student", "service"]))
    me = client.get("/api/v1/identity/auth/me", headers=token).json()
    # /auth/me shows the stored row, which still lists the legacy role; what matters is that it grants nothing.
    assert "service" in me["roles"] and PROBE not in me["permissions"]
    assert client.post("/api/v1/identity/users", json=_new_user(["student"]), headers=token).status_code == 403
