"""GET /faculty-load end to end (FR-13): the report is computed from stored assignments, filtered (never authorised)
by department_id, and refuses honestly when no faculty directory is available."""

from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, assign, make_course, make_offering, make_term, ok  # noqa: E402

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
from eos_core.db import new_id  # noqa: E402

HOD = "department-admin"


@pytest.fixture
def staffed(client, org):
    """Two departments' offerings in the active term: f1 teaches 12 + 8 hours (over 18), f2 teaches 6 hours."""
    _, admin = org.user("org-admin")
    _, h = org.user(HOD)
    term = make_term(client, admin)
    ok(client.post(f"{BASE}/terms/{term['id']}/activate", headers=admin))
    dept_x, dept_y = new_id(), new_id()
    c1 = make_course(client, admin, "C1", department_id=dept_x)
    c2 = make_course(client, admin, "C2", department_id=dept_y)
    o1 = make_offering(client, h, c1["id"], term["id"])
    o2 = make_offering(client, h, c2["id"], term["id"])
    f1, _ = org.user("faculty", name="A. Rao")
    f2, _ = org.user("faculty", name="B. Iyer")
    assign(client, h, o1["id"], f1, hours=12)
    assign(client, h, o2["id"], f1, hours=8)
    assign(client, h, o1["id"], f2, role="co_instructor", hours=6)
    assign(client, h, o2["id"], f2, role="teaching_assistant", hours=10)  # does not count
    return {"h": h, "term": term, "dept_x": dept_x, "dept_y": dept_y, "f1": f1, "f2": f2}


def test_the_report_for_the_active_term(client, staffed):
    s = staffed
    body = ok(client.get(f"{BASE}/faculty-load", headers=s["h"]))
    assert (body["academic_period_id"], body["academic_period_code"], body["max_weekly_contact_hours"]) == (
        s["term"]["id"],
        "2026-ODD",
        18,
    )
    assert [(i["faculty_name"], i["contact_hours"], i["offerings_count"], i["over_load"]) for i in body["items"]] == [
        ("A. Rao", 20, 2, True),
        ("B. Iyer", 6, 1, False),
    ]
    assert (body["faculty_count"], body["over_load_count"]) == (2, 1)


def test_over_load_only_keeps_the_counts(client, staffed):
    body = ok(client.get(f"{BASE}/faculty-load?over_load_only=true", headers=staffed["h"]))
    assert [i["faculty_name"] for i in body["items"]] == ["A. Rao"]
    assert (body["faculty_count"], body["over_load_count"]) == (2, 1)


def test_department_id_narrows_the_report(client, staffed):
    s = staffed
    body = ok(client.get(f"{BASE}/faculty-load?department_id={s['dept_y']}", headers=s["h"]))
    assert body["department_id"] == s["dept_y"]
    assert [(i["faculty_name"], i["contact_hours"]) for i in body["items"]] == [("A. Rao", 8)]


@pytest.mark.parametrize("role", ["faculty", "student", "examination-staff"])
def test_a_department_id_is_never_proof_of_access(client, staffed, org, role):
    _, h = org.user(role)
    r = client.get(f"{BASE}/faculty-load?department_id={staffed['dept_x']}", headers=h)
    assert r.status_code == 403  # access is the faculty-load:read key alone


def test_org_admin_and_department_admin_hold_the_key(client, staffed, org):
    for role in ("org-admin", "department-admin"):
        _, h = org.user(role)
        assert client.get(f"{BASE}/faculty-load", headers=h).status_code == 200


def test_no_active_term_is_404_active_term_not_found(client, org):
    _, h = org.user(HOD)
    r = client.get(f"{BASE}/faculty-load", headers=h)
    assert (r.status_code, r.json()["detail"]["code"]) == (404, "active_term_not_found")
    r = client.get(f"{BASE}/faculty-load?academic_period_id={new_id()}", headers=h)
    assert r.status_code == 404


def test_ids_must_be_uuids(client, org):
    _, h = org.user(HOD)
    assert client.get(f"{BASE}/faculty-load?department_id=not-a-uuid", headers=h).status_code == 422


def test_without_a_faculty_directory_names_are_refused_not_guessed(client, staffed):
    from eos_academic_management.api.router import faculty_directory

    app = client.app
    override = app.dependency_overrides.pop(faculty_directory)
    try:
        r = client.get(f"{BASE}/faculty-load", headers=staffed["h"])
        assert (r.status_code, r.json()["detail"]["code"]) == (503, "faculty_directory_unavailable")
        declared = CONTRACT["paths"]["/faculty-load"]["get"]["responses"]
        assert declared["503"]["content"]["application/json"]["schema"] == {
            "$ref": "#/components/schemas/ErrorResponse"
        }
    finally:
        app.dependency_overrides[faculty_directory] = override


def test_every_status_the_route_returns_is_declared_in_the_contract():
    declared = set(CONTRACT["paths"]["/faculty-load"]["get"]["responses"])
    assert {"200", "403", "404", "503"} <= declared  # 422 for a malformed id is FastAPI's (shared error format)
