"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see test_api_deps.py)")

from conftest import BASE, make_course, make_offering, make_programme, make_term, ok  # noqa: E402
from eos_core.db import new_id  # noqa: E402
from eos_testing import assert_no_cross_tenant_leak  # noqa: E402


def seed(client, org) -> tuple[str, dict]:
    _, admin = org.user("org-admin")
    term = make_term(client, admin)
    course = make_course(client, admin)
    programme = make_programme(client, admin)
    offering = make_offering(client, admin, course["id"], term["id"])
    curriculum = ok(client.post(f"{BASE}/programmes/{programme['id']}/curricula", json={}, headers=admin), 201)
    return admin["Authorization"].split(" ", 1)[1], {
        "term": term,
        "course": course,
        "programme": programme,
        "offering": offering,
        "curriculum": curriculum,
        "section": offering["sections"][0],
    }


def test_no_cross_tenant_leak(client, org, other_org):
    token_a, a = seed(client, org)
    token_b, b = seed(client, other_org)
    for path in ("/terms", "/programmes", "/courses", "/offerings"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token_a, token_b)
    as_b = {"Authorization": f"Bearer {token_b}"}
    for path in (
        f"/terms/{a['term']['id']}",
        f"/programmes/{a['programme']['id']}",
        f"/programmes/{a['programme']['id']}/curricula",
        f"/courses/{a['course']['id']}",
        f"/curricula/{a['curriculum']['id']}",
        f"/offerings/{a['offering']['id']}",
        f"/offerings/{a['offering']['id']}/sections",
        f"/offerings/{a['offering']['id']}/faculty-assignments",
        f"/offerings/{a['offering']['id']}/roster",
    ):
        assert client.get(f"{BASE}{path}", headers=as_b).status_code == 404, path
    # writes against another organisation's ids find nothing
    assert client.post(f"{BASE}/terms/{a['term']['id']}/activate", headers=as_b).status_code == 404
    assert client.post(f"{BASE}/courses/{a['course']['id']}/archive", headers=as_b).status_code == 404
    assert (
        client.patch(f"{BASE}/sections/{a['section']['id']}", json={"status": "closed"}, headers=as_b).status_code
        == 404
    )
    cross = client.post(
        f"{BASE}/offerings",
        json={
            "course_id": a["course"]["id"],
            "academic_period_id": b["term"]["id"],
            "sections": [{"code": "A", "capacity": 1}],
        },
        headers=as_b,
    )
    assert (cross.status_code, cross.json()["detail"]["code"]) == (400, "unknown_course")
    assign = client.post(
        f"{BASE}/offerings/{a['offering']['id']}/faculty-assignments",
        json={"faculty_id": new_id(), "role": "primary", "contact_hours": 1},
        headers=as_b,
    )
    assert assign.status_code == 404
    assert b["term"]["organisation_id"] == other_org.id


def test_a_client_supplied_organisation_id_is_ignored(client, org, other_org):
    """The organisation always comes from the verified token, never from the request body."""
    _, admin = org.user("org-admin")
    body = {
        "code": "T",
        "name": "T",
        "starts_on": "2031-01-01",
        "ends_on": "2031-02-01",
        "organisation_id": other_org.id,
    }
    r = client.post(f"{BASE}/terms", json=body, headers=admin)
    assert r.status_code == 422  # unknown fields are refused outright
