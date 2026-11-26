"""The faculty-load report names faculty from identity (apps/backend/src/eos_backend/directories.py).

academic-management cannot import identity, so its `faculty_directory` dependency refuses (503) unless the host
overrides it. Without the override the Department Admin dashboard's faculty-load widget failed as soon as one faculty
member was assigned."""

import uuid

from eos_testing import register_and_login
from eos_testing.tenancy import auth

AM = "/api/v1/academic-management"


def _user(client, admin, name: str, role: str) -> dict:
    body = {
        "email": f"{uuid.uuid4().hex[:8]}@faculty.example.com",
        "name": name,
        "password": "Passw0rd!x",
        "roles": [role],
    }
    r = client.post("/api/v1/identity/users", json=body, headers=admin)
    assert r.status_code == 201, r.text
    return r.json()


def _assign(client, admin, faculty_id: str) -> None:
    dept = str(uuid.uuid4())
    term = client.post(
        f"{AM}/terms",
        json={"code": "2026-ODD", "name": "Odd 2026", "starts_on": "2026-07-01", "ends_on": "2026-12-15"},
        headers=admin,
    )
    assert term.status_code == 201, term.text
    activated = client.post(f"{AM}/terms/{term.json()['id']}/activate", headers=admin)
    assert activated.status_code == 200, activated.text
    course = client.post(
        f"{AM}/courses",
        json={"code": "CS101", "title": "Intro", "credits": 3, "course_type": "theory", "department_id": dept},
        headers=admin,
    )
    assert course.status_code == 201, course.text
    offering = client.post(
        f"{AM}/offerings",
        json={
            "course_id": course.json()["id"],
            "academic_period_id": term.json()["id"],
            "sections": [{"code": "A", "capacity": 40}],
        },
        headers=admin,
    )
    assert offering.status_code == 201, offering.text
    assigned = client.post(
        f"{AM}/offerings/{offering.json()['id']}/faculty-assignments",
        json={"faculty_id": faculty_id, "role": "primary", "contact_hours": 6},
        headers=admin,
    )
    assert assigned.status_code == 201, assigned.text


def test_faculty_load_names_the_assigned_faculty_member(client):
    a = register_and_login(client, slug="fl-names")
    admin = auth(a["token"])
    teacher = _user(client, admin, "Asha Rao", "faculty")
    _assign(client, admin, teacher["id"])

    r = client.get(f"{AM}/faculty-load", headers=admin)

    assert r.status_code == 200, r.text  # was 503 faculty_directory_unavailable
    items = r.json()["items"]
    assert [i["faculty_name"] for i in items] == ["Asha Rao"]


def test_a_faculty_id_from_another_organisation_is_not_named(client):
    mine = register_and_login(client, slug="fl-mine")
    theirs = register_and_login(client, slug="fl-theirs")
    outsider = _user(client, auth(theirs["token"]), "Other Tenant Person", "faculty")
    admin = auth(mine["token"])
    _assign(client, admin, outsider["id"])  # an id the module cannot check: identity is not its to ask

    r = client.get(f"{AM}/faculty-load", headers=admin)

    assert r.status_code == 200, r.text
    names = [i["faculty_name"] for i in r.json()["items"]]
    assert "Other Tenant Person" not in names
    assert names == ["Unknown user"]


def test_the_host_wires_lookups_without_dependency_overrides():
    """FastAPI rebuilds every dependency of every request, in every module, as soon as app.dependency_overrides is
    not empty (FastAPI 0.142, solve_dependencies): about 9 % of the API's CPU on 20 Nov (tests/performance). The
    host gives modules their lookups through app.state instead, so production wiring leaves the dict empty."""
    from eos_backend import directories
    from eos_backend.main import create_app

    app = create_app()
    assert app.dependency_overrides == {}
    assert app.state.faculty_directory is directories.faculty_directory
