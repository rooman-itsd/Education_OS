"""Tests of the API access layer: who is calling (401, 403) and the permission guard (403), on a test-only route.
Permission keys are resolved by eos_core.permissions_for from contracts/permissions.yaml, whose role blocks are
platform role ids; tokens carry those ids, as a signed-in user's token does."""

import jwt
import pytest

pytest.importorskip(
    "eos_core",
    reason='needs eos_core: PYTHONPATH="src;../../../../packages/core/src;../../../../packages/testing/src"',
)

from eos_academic_management.api.deps import current_actor, require  # noqa: E402
from eos_academic_management.application.access import FACULTY_LOAD_READ, ROSTER_READ, ROSTER_READ_ALL  # noqa: E402
from eos_core.db import get_db, new_id  # noqa: E402
from eos_core.security import create_token  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

HEAD = "department-admin"
FACULTY = "faculty"
VIEWER = "student"


def probe_app() -> FastAPI:
    """Two routes that exist only in this test: one guarded by faculty-load:read, one by either roster key."""
    app = FastAPI()

    @app.get("/load")
    def load(actor=Depends(require(FACULTY_LOAD_READ)), db=Depends(get_db)):
        return {
            "user_id": actor.user_id,
            "organisation_id": actor.organisation_id,
            "has_key": actor.can(FACULTY_LOAD_READ),
            "session_organisation": db.info.get("organisation_id"),
        }

    @app.get("/roster")
    def roster(actor=Depends(require(ROSTER_READ, ROSTER_READ_ALL))):
        return {"ok": True}

    @app.get("/me")
    def me(actor=Depends(current_actor)):
        return {"roles": actor.roles}

    return app


@pytest.fixture(scope="module")
def client():
    with TestClient(probe_app()) as c:
        yield c


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def token(*roles: str, organisation_id: str | None = "org-1", **kwargs) -> str:
    return create_token(user_id=new_id(), organisation_id=organisation_id, roles=list(roles), **kwargs)


# --- 401: no valid authentication


@pytest.mark.parametrize("headers", [{}, {"Authorization": ""}, {"Authorization": "Basic dXNlcjpwYXNz"}])
def test_missing_bearer_token_is_401(client, headers):
    assert client.get("/load", headers=headers).status_code == 401


def test_a_token_that_is_not_a_jwt_is_401(client):
    response = client.get("/load", headers=bearer("not-a-token"))
    assert response.status_code == 401
    assert "invalid token" in response.json()["detail"]


def test_a_token_signed_with_another_key_is_401(client):
    forged = jwt.encode({"sub": "u1", "org": "org-1", "roles": [HEAD]}, "some-other-key-of-at-least-32-bytes", "HS256")
    assert client.get("/load", headers=bearer(forged)).status_code == 401


def test_an_expired_token_is_401(client):
    assert client.get("/load", headers=bearer(token(HEAD, ttl_minutes=-1))).status_code == 401


def test_a_token_without_a_subject_is_401_not_500(client):
    from eos_core.settings import settings

    no_subject = jwt.encode({"org": "org-1", "roles": [HEAD], "exp": 4102444800}, settings.jwt_secret, "HS256")
    response = client.get("/load", headers=bearer(no_subject))
    assert (response.status_code, response.json()["detail"]) == (401, "invalid token: no subject")


# --- 403: no organisation, or no permission


@pytest.mark.parametrize("organisation_id", [None, ""])
def test_a_user_without_an_organisation_is_403(client, organisation_id):
    response = client.get("/me", headers=bearer(token(HEAD, organisation_id=organisation_id)))
    assert response.status_code == 403


def test_a_caller_without_the_key_is_403_with_the_contract_error_body(client):
    response = client.get("/load", headers=bearer(token(FACULTY)))  # faculty does not hold faculty-load:read
    assert response.status_code == 403
    assert response.json()["detail"] == {"code": "forbidden", "message": f"requires {FACULTY_LOAD_READ}"}


@pytest.mark.parametrize("roles", [(), ("no-such-role",)])
def test_unknown_or_no_roles_grant_nothing(client, roles):
    assert client.get("/load", headers=bearer(token(*roles))).status_code == 403


# --- allowed: keys resolved from contracts/permissions.yaml


def test_a_platform_role_token_resolves_its_keys_and_the_session_carries_the_organisation(client):
    response = client.get("/load", headers=bearer(token(HEAD, organisation_id="org-7")))
    assert response.status_code == 200
    body = response.json()
    assert body["has_key"] is True
    assert body["organisation_id"] == body["session_organisation"] == "org-7"


@pytest.mark.parametrize(("role", "status"), [(FACULTY, 200), (HEAD, 200), (VIEWER, 403)])
def test_any_one_of_several_keys_is_enough(client, role, status):
    # faculty holds roster:read, the department head roster:read-all, the viewer neither
    assert client.get("/roster", headers=bearer(token(role))).status_code == status


# --- the guard itself


@pytest.mark.parametrize("keys", [(), ("academic-management:faculty-load:write",), ("faculty-load:read",)])
def test_require_refuses_keys_outside_the_catalogue(keys):
    with pytest.raises(ValueError, match="contracts/permissions.yaml"):
        require(*keys)
