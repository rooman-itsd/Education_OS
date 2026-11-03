"""Authentication and permission checks of the API layer (api/deps.py)."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

import jwt  # noqa: E402
from conftest import ADMIN, BASE, FACULTY, ok  # noqa: E402
from eos_core.db import new_id  # noqa: E402
from eos_core.security import create_token  # noqa: E402
from eos_core.settings import settings  # noqa: E402
from eos_timetable_attendance.api.deps import require  # noqa: E402
from eos_timetable_attendance.application import access  # noqa: E402


def test_no_token_or_a_bad_token_is_401(client):
    assert client.get(f"{BASE}/timetables").status_code == 401
    assert client.get(f"{BASE}/timetables", headers={"Authorization": "Token abc"}).status_code == 401
    assert client.get(f"{BASE}/timetables", headers={"Authorization": "Bearer abc"}).status_code == 401
    forged = jwt.encode(
        {"sub": new_id(), "org": new_id(), "roles": [ADMIN]}, "another-key-another-key-another-key", algorithm="HS256"
    )
    assert client.get(f"{BASE}/timetables", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_a_token_without_a_subject_is_401_and_without_an_organisation_is_403(client):
    no_subject = jwt.encode({"org": new_id(), "roles": [ADMIN]}, settings.jwt_secret, algorithm="HS256")
    assert client.get(f"{BASE}/timetables", headers={"Authorization": f"Bearer {no_subject}"}).status_code == 401
    platform_user = create_token(user_id=new_id(), organisation_id=None, roles=[ADMIN])
    assert client.get(f"{BASE}/timetables", headers={"Authorization": f"Bearer {platform_user}"}).status_code == 403


def test_the_role_decides_the_keys_and_a_403_carries_the_contract_body(client, org):
    _, student = org.user("timetable-attendance-student")
    r = client.get(f"{BASE}/timetables", headers=student)
    assert r.status_code == 403
    assert r.json()["detail"] == {"code": "forbidden", "message": f"requires {access.TIMETABLE_READ}"}
    _, faculty = org.user(FACULTY)
    ok(client.get(f"{BASE}/timetables", headers=faculty))


def test_an_unknown_role_holds_no_key(client, org):
    _, nobody = org.user("not-a-role")
    assert client.get(f"{BASE}/timetables", headers=nobody).status_code == 403


def test_require_refuses_keys_outside_the_catalogue_when_the_route_is_defined():
    with pytest.raises(ValueError):
        require("timetable-attendance:timetable:destroy")
    with pytest.raises(ValueError):
        require()
    both = require(access.TIMETABLE_READ, access.TIMETABLE_WRITE)
    assert both.permissions == {access.TIMETABLE_READ, access.TIMETABLE_WRITE}
