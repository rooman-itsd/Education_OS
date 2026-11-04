"""Authentication and permission checks of the API layer (api/deps.py), on a small app with two guarded routes: the
module's routes come in a later slice, and this is the guard they will all use."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

import jwt  # noqa: E402
from conftest import uid  # noqa: E402
from eos_core.db import get_db  # noqa: E402
from eos_core.security import create_token  # noqa: E402
from eos_core.settings import settings  # noqa: E402
from eos_examinations.api.deps import current_actor, require  # noqa: E402
from eos_examinations.application import access  # noqa: E402
from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

app = FastAPI()


@app.get("/cycles")
def cycles(actor: access.Actor = Depends(require(access.EXAM_CYCLE_READ))):
    return {"user": actor.user_id, "organisation": actor.organisation_id, "roles": actor.roles}


@app.get("/duties")
def duties(actor: access.Actor = Depends(require(access.DUTY_READ_OWN, access.DUTY_READ_ALL))):
    return {"ok": True}


@app.get("/tenant")
def tenant(actor: access.Actor = Depends(current_actor), db=Depends(get_db)):
    return {"session_organisation": db.info.get("organisation_id")}


client = TestClient(app)


def bearer(*roles: str, user_id: str | None = None, organisation_id: str | None = "o1") -> dict:
    return {
        "Authorization": f"Bearer {create_token(user_id=user_id or uid(), organisation_id=organisation_id, roles=list(roles))}"
    }


def test_no_token_or_a_bad_one_is_401():
    assert client.get("/cycles").status_code == 401
    assert client.get("/cycles", headers={"Authorization": "Token abc"}).status_code == 401
    assert client.get("/cycles", headers={"Authorization": "Bearer abc"}).status_code == 401
    forged = jwt.encode(
        {"sub": uid(), "org": "o", "roles": ["examinations-controller"]},
        "another-key-another-key-another-key",
        algorithm="HS256",
    )
    assert client.get("/cycles", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_a_token_without_a_subject_is_401_and_without_an_organisation_is_403():
    no_subject = jwt.encode({"org": "o", "roles": ["examinations-controller"]}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/cycles", headers={"Authorization": f"Bearer {no_subject}"}).status_code == 401
    assert client.get("/cycles", headers=bearer("examinations-controller", organisation_id=None)).status_code == 403


def test_the_role_decides_the_keys_and_a_403_carries_the_contract_body():
    assert client.get("/cycles", headers=bearer("examinations-viewer")).status_code == 200  # holds exam-cycle:read
    r = client.get("/cycles", headers=bearer("examinations-student"))
    assert r.status_code == 403
    assert r.json()["detail"] == {"code": "forbidden", "message": f"requires {access.EXAM_CYCLE_READ}"}
    assert client.get("/cycles", headers=bearer("not-a-role")).status_code == 403


def test_a_route_may_accept_any_of_several_keys():
    assert client.get("/duties", headers=bearer("examinations-faculty")).status_code == 200  # duty:read-own
    assert client.get("/duties", headers=bearer("examinations-controller")).status_code == 200  # duty:read-all
    assert client.get("/duties", headers=bearer("examinations-student")).status_code == 403


def test_the_actor_and_the_session_organisation_come_from_the_token_only():
    user = uid()
    body = client.get(
        "/cycles",
        headers={**bearer("examinations-viewer", user_id=user, organisation_id="org-a"), "X-Organisation-Id": "org-b"},
    ).json()
    assert (body["user"], body["organisation"], body["roles"]) == (user, "org-a", ["examinations-viewer"])
    seen = client.get(
        "/tenant", headers={**bearer("examinations-viewer", organisation_id="org-a"), "X-Organisation-Id": "org-b"}
    ).json()
    assert seen == {"session_organisation": "org-a"}


def test_require_refuses_keys_outside_the_catalogue_when_the_route_is_defined():
    with pytest.raises(ValueError):
        require("examinations:exam-cycle:destroy")
    with pytest.raises(ValueError):
        require()
    both = require(access.EXAM_CYCLE_READ, access.EXAM_CYCLE_MANAGE)
    assert both.permissions == {access.EXAM_CYCLE_READ, access.EXAM_CYCLE_MANAGE}
