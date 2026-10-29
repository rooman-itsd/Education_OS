"""Routes over HTTP: authentication, the permission each route needs, validation, and the contract's status codes
and {code, message} error bodies."""

from __future__ import annotations

import pytest
from conftest import BASE, EXAM_STAFF, MANAGEMENT, NO_ACCESS, add_enrolment, add_window, headers, mint_token, seed
from eos_core.db import new_id

UUID = "00000000-0000-4000-8000-000000000001"
REGISTRATION_BODY = {
    "programme_enrolment_id": UUID,
    "course_offering_id": UUID,
    "section_id": UUID,
    "academic_period_id": UUID,
}
READS = [
    ("get", "/programme-enrolments", None),
    ("get", "/programme-enrolments/{id}", None),
    ("get", "/terms/{id}/registration-window", None),
    ("get", "/registrations", None),
    ("get", "/registrations/{id}", None),
    ("get", "/reports/registered-candidates", None),
]
MANAGES = [
    (
        "post",
        "/programme-enrolments",
        {"person_id": UUID, "student_name": "A", "programme_id": UUID, "start_academic_period_id": UUID},
    ),
    ("post", "/programme-enrolments/{id}/withdraw", {"reason": "r"}),
    ("post", "/programme-enrolments/{id}/complete", None),
    (
        "put",
        "/terms/{id}/registration-window",
        {"opens_at": "2026-10-01T00:00:00Z", "closes_at": "2026-10-10T00:00:00Z"},
    ),
    ("post", "/registrations", REGISTRATION_BODY),
    ("post", "/registrations/bulk", {**REGISTRATION_BODY, "programme_enrolment_ids": [UUID]}),
    ("post", "/registrations/{id}/withdraw", {"reason": "r"}),
    ("post", "/registrations/{id}/change-section", {"to_section_id": UUID, "effective_on": "2026-11-02"}),
]


def call(client, method, path, body, h=None):
    kwargs = {"headers": h or {}}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(BASE + path.format(id=new_id()), **kwargs)


@pytest.mark.parametrize(("method", "path", "body"), READS + MANAGES)
def test_every_route_needs_a_valid_token_an_organisation_and_a_permission(client, method, path, body):
    assert call(client, method, path, body).status_code == 401
    forged = {"Authorization": f"Bearer {mint_token(new_id(), ['registration-staff'], secret='x' * 40)}"}
    assert call(client, method, path, body, forged).status_code == 401
    assert call(client, method, path, body, headers(None)).status_code == 403
    assert call(client, method, path, body, headers(new_id(), NO_ACCESS)).status_code == 403


@pytest.mark.parametrize(("method", "path", "body"), MANAGES)
def test_read_only_roles_cannot_change_anything(client, method, path, body):
    for role in (EXAM_STAFF, MANAGEMENT):
        assert call(client, method, path, body, headers(new_id(), role)).status_code == 403


def test_examination_staff_reads_registrations_but_not_enrolments(client):
    h = headers(new_id(), EXAM_STAFF)
    assert client.get(f"{BASE}/registrations", headers=h).status_code == 200
    assert client.get(f"{BASE}/reports/registered-candidates", headers=h).status_code == 200
    assert client.get(f"{BASE}/programme-enrolments", headers=h).status_code == 403
    assert client.get(f"{BASE}/programme-enrolments", headers=headers(new_id(), MANAGEMENT)).status_code == 200


def test_enrolment_journey(client, org):
    h = headers(org)
    body = {
        "person_id": new_id(),
        "student_name": "Ana Silva",
        "programme_id": new_id(),
        "start_academic_period_id": new_id(),
    }
    made = client.post(f"{BASE}/programme-enrolments", json=body, headers=h)
    assert made.status_code == 201 and made.json()["roll_number"].startswith("RN")
    again = client.post(f"{BASE}/programme-enrolments", json=body, headers=h)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "duplicate_enrolment"
    eid = made.json()["id"]
    assert client.get(f"{BASE}/programme-enrolments/{eid}", headers=h).json()["id"] == eid
    assert client.get(f"{BASE}/programme-enrolments", params={"q": "ana"}, headers=h).json()["total"] == 1
    assert (
        client.post(f"{BASE}/programme-enrolments/{eid}/withdraw", json={"reason": " "}, headers=h).status_code == 422
    )
    assert (
        client.post(f"{BASE}/programme-enrolments/{eid}/withdraw", json={"reason": "left"}, headers=h).status_code
        == 200
    )
    ended = client.post(f"{BASE}/programme-enrolments/{eid}/complete", headers=h)
    assert ended.status_code == 409 and ended.json()["detail"]["code"] == "enrolment_ended"
    missing = client.get(f"{BASE}/programme-enrolments/{new_id()}", headers=h)
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "not_found"


def test_window_routes(client, org):
    h, term = headers(org), new_id()
    url = f"{BASE}/terms/{term}/registration-window"
    assert client.get(url, headers=h).status_code == 404
    naive = client.put(url, json={"opens_at": "2026-10-01T00:00:00", "closes_at": "2026-10-10T00:00:00"}, headers=h)
    assert naive.status_code == 422
    backwards = client.put(
        url, json={"opens_at": "2026-10-10T00:00:00Z", "closes_at": "2026-10-01T00:00:00Z"}, headers=h
    )
    assert backwards.status_code == 422 and backwards.json()["detail"]["code"] == "invalid_window"
    ok = client.put(url, json={"opens_at": "2026-10-01T00:00:00Z", "closes_at": "2099-10-10T00:00:00Z"}, headers=h)
    assert ok.status_code == 200 and ok.json()["is_open"] is True
    assert client.get(f"{BASE}/terms/not-a-uuid/registration-window", headers=h).status_code == 422


def test_registration_journey(client, org):
    h, term = headers(org), new_id()
    seed(add_window, org, term)
    student = seed(add_enrolment, org)
    body = {
        "programme_enrolment_id": student.id,
        "course_offering_id": new_id(),
        "section_id": new_id(),
        "academic_period_id": term,
    }
    made = client.post(f"{BASE}/registrations", json=body, headers=h)
    assert made.status_code == 201 and made.json()["roll_number"] == student.roll_number
    dup = client.post(f"{BASE}/registrations", json={**body, "section_id": new_id()}, headers=h)
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "already_registered"
    assert (
        client.post(f"{BASE}/registrations", json={**body, "registration_type": "elective"}, headers=h).status_code
        == 422
    )
    rid = made.json()["id"]
    moved = client.post(
        f"{BASE}/registrations/{rid}/change-section",
        json={"to_section_id": new_id(), "effective_on": "2026-11-02"},
        headers=h,
    )
    assert moved.status_code == 200 and moved.json()["section_since"] == "2026-11-02"
    listed = client.get(f"{BASE}/registrations", params={"academic_period_id": term}, headers=h).json()
    assert listed["total"] == 1 and listed["items"][0]["id"] == rid
    assert (
        client.post(f"{BASE}/registrations/{rid}/withdraw", json={"reason": "drop"}, headers=h).json()["status"]
        == "withdrawn"
    )
    again = client.post(f"{BASE}/registrations/{rid}/withdraw", json={"reason": "drop"}, headers=h)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "registration_not_confirmed"


def test_bulk_route(client, org):
    h, term = headers(org), new_id()
    seed(add_window, org, term)
    a, b = seed(add_enrolment, org), seed(add_enrolment, org)
    body = {
        "programme_enrolment_ids": [a.id, b.id, a.id],
        "course_offering_id": new_id(),
        "section_id": new_id(),
        "academic_period_id": term,
    }
    result = client.post(f"{BASE}/registrations/bulk", json=body, headers=h)
    assert result.status_code == 200
    assert (result.json()["confirmed"], result.json()["refused"]) == (2, 0)
    assert (
        client.post(f"{BASE}/registrations/bulk", json={**body, "programme_enrolment_ids": []}, headers=h).status_code
        == 422
    )
    too_many = {**body, "programme_enrolment_ids": [new_id() for _ in range(501)]}
    assert client.post(f"{BASE}/registrations/bulk", json=too_many, headers=h).status_code == 422


def test_report_route(client, org):
    h = headers(org)
    report = client.get(f"{BASE}/reports/registered-candidates", params={"limit": 3}, headers=h)
    assert report.status_code == 200 and report.json()["total"] == 0
    assert client.get(f"{BASE}/reports/registered-candidates", params={"limit": 51}, headers=h).status_code == 422
    assert (
        client.get(f"{BASE}/reports/registered-candidates", params={"academic_period_id": "x"}, headers=h).status_code
        == 422
    )
