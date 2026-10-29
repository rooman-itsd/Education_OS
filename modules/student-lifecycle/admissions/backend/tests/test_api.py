"""Staff routes over HTTP: authentication, permission per route, validation, and the contract's status codes
and {code, message} error bodies."""

from __future__ import annotations

from datetime import timedelta

import pytest
from conftest import (
    BASE,
    MANAGEMENT,
    NO_ACCESS,
    REVIEWER,
    add_application,
    add_document,
    headers,
    mint_token,
    seed,
)
from eos_admissions.domain import enums as e
from eos_core.db import new_id, utcnow

ROUTES = [
    ("get", "/applications", None),
    ("get", "/applications/{id}", None),
    ("put", "/applications/{id}/status", {"status": "under_review", "reason": "r"}),
    ("post", "/applications/{id}/documents/{doc}/verify", {"verification_status": "verified"}),
    ("post", "/applications/{id}/offer", {}),
    ("get", "/merit-lists", None),
    ("post", "/merit-lists", {"programme_id": "00000000-0000-4000-8000-000000000001", "academic_year": "2026-27"}),
    ("get", "/merit-lists/{id}", None),
    ("post", "/merit-lists/{id}/publish", None),
    ("get", "/documents", None),
]
FUNNEL = ("get", "/reports/funnel", None)


def test_funnel_needs_a_token_and_report_permission(client):
    assert call(client, *FUNNEL).status_code == 401
    assert call(client, *FUNNEL, headers(new_id(), NO_ACCESS)).status_code == 403
    assert call(client, *FUNNEL, headers(new_id(), REVIEWER)).status_code == 403
    assert call(client, *FUNNEL, headers(new_id(), MANAGEMENT)).status_code == 200


def test_management_sees_counts_but_no_applicant_data(client, org):
    seed(add_application, org, status=e.ELIGIBLE)
    h = headers(org, MANAGEMENT)
    report = client.get(f"{BASE}/reports/funnel", headers=h).json()
    assert report["total"] == 1 and report["stages"]["eligible"] == 1
    assert "Ana" not in str(report) and "example.com" not in str(report)
    assert client.get(f"{BASE}/applications", headers=h).status_code == 403
    assert client.get(f"{BASE}/documents", headers=h).status_code == 403


def test_report_and_queue_query_validation(client, org):
    h = headers(org)
    assert client.get(f"{BASE}/reports/funnel", params={"programme_id": "x"}, headers=h).status_code == 422
    assert client.get(f"{BASE}/documents", params={"verification_status": "lost"}, headers=h).status_code == 422
    assert client.get(f"{BASE}/documents", params={"page_size": 201}, headers=h).status_code == 422
    assert client.get(f"{BASE}/documents", headers=headers(org, REVIEWER)).status_code == 200


def call(client, method, path, body, h=None):
    url = BASE + path.format(id=new_id(), doc=new_id())
    kwargs = {"headers": h or {}}
    if body is not None:
        kwargs["json"] = body
    return getattr(client, method)(url, **kwargs)


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_every_staff_route_needs_a_token(client, method, path, body):
    assert call(client, method, path, body).status_code == 401
    bad = {"Authorization": f"Bearer {mint_token(new_id(), ['admissions-staff'], secret='x' * 40)}"}
    assert call(client, method, path, body, bad).status_code == 401


@pytest.mark.parametrize(("method", "path", "body"), ROUTES)
def test_every_staff_route_needs_an_organisation_and_a_permission(client, method, path, body):
    assert call(client, method, path, body, headers(None)).status_code == 403
    assert call(client, method, path, body, headers(new_id(), NO_ACCESS)).status_code == 403
    assert call(client, method, path, body, headers(new_id(), MANAGEMENT)).status_code == 403


def test_reviewer_can_read_and_verify_but_not_decide(client, org):
    app_id = seed(add_application, org, status=e.ELIGIBLE)
    h = headers(org, REVIEWER)
    assert client.get(f"{BASE}/applications/{app_id}", headers=h).status_code == 200
    assert client.post(f"{BASE}/applications/{app_id}/offer", headers=h).status_code == 403
    assert (
        client.put(
            f"{BASE}/applications/{app_id}/status", json={"status": "withdrawn", "reason": "r"}, headers=h
        ).status_code
        == 403
    )


def test_list_and_get(client, org):
    app_id = seed(add_application, org, status=e.ELIGIBLE)
    seed(add_application, org)
    h = headers(org)
    body = client.get(f"{BASE}/applications", params={"status": "eligible,offered"}, headers=h).json()
    assert body["total"] == 1 and body["items"][0]["id"] == app_id
    assert client.get(f"{BASE}/applications", params={"status": "nope"}, headers=h).status_code == 422
    assert client.get(f"{BASE}/applications", params={"page_size": 500}, headers=h).status_code == 422
    assert client.get(f"{BASE}/applications", params={"programme_id": "not-a-uuid"}, headers=h).status_code == 422
    one = client.get(f"{BASE}/applications/{app_id}", headers=h)
    assert one.status_code == 200 and one.json()["documents"] == [] and one.json()["offer"] is None
    missing = client.get(f"{BASE}/applications/{new_id()}", headers=h)
    assert missing.status_code == 404 and missing.json()["detail"]["code"] == "not_found"


def test_status_change(client, org):
    app_id = seed(add_application, org)
    h = headers(org)
    url = f"{BASE}/applications/{app_id}/status"
    assert (
        client.put(url, json={"status": "under_review", "reason": "ok"}, headers=h).json()["status"] == "under_review"
    )
    assert client.put(url, json={"status": "under_review", "reason": ""}, headers=h).status_code == 422
    assert client.put(url, json={"status": "bogus", "reason": "r"}, headers=h).status_code == 422
    invalid = client.put(url, json={"status": "offered", "reason": "r"}, headers=h)
    assert invalid.status_code == 422 and invalid.json()["detail"]["code"] == "invalid_transition"
    blank = client.put(url, json={"status": "eligible", "reason": "   "}, headers=h)
    assert blank.status_code == 422 and blank.json()["detail"]["code"] == "reason_required"
    client.put(url, json={"status": "rejected", "reason": "r"}, headers=h)
    terminal = client.put(url, json={"status": "under_review", "reason": "r"}, headers=h)
    assert terminal.status_code == 409 and terminal.json()["detail"] == {
        "code": "terminal_status",
        "message": terminal.json()["detail"]["message"],
    }


def test_verify_document(client, org):
    def seed_doc(session, organisation_id):
        return add_document(session, add_application(session, organisation_id, status=e.UNDER_REVIEW))

    from conftest import SessionLocal
    from eos_admissions.infrastructure.models import ApplicationDocument

    doc_id = seed(seed_doc, org)
    with SessionLocal() as s:
        app_id = s.get(ApplicationDocument, doc_id).application_id
    url = f"{BASE}/applications/{app_id}/documents/{doc_id}/verify"
    h = headers(org)
    ok = client.post(url, json={"verification_status": "verified", "verification_note": "fine"}, headers=h)
    assert ok.status_code == 200 and ok.json()["verification_status"] == "verified"
    assert client.post(url, json={"verification_status": "pending"}, headers=h).status_code == 422


def test_offer(client, org):
    app_id = seed(add_application, org, status=e.ELIGIBLE)
    h = headers(org)
    url = f"{BASE}/applications/{app_id}/offer"
    past = (utcnow() - timedelta(days=1)).isoformat()
    assert client.post(url, json={"expires_at": past}, headers=h).status_code == 422
    assert client.post(url, json={"expires_at": "2030-01-01T00:00:00"}, headers=h).status_code == 422
    made = client.post(url, headers=h)
    assert made.status_code == 201 and made.json()["status"] == "offered"
    again = client.post(url, json={"note": "second"}, headers=h)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "offer_already_exists"


def test_merit_lists(client, org):
    programme = new_id()
    eligible = seed(add_application, org, programme_id=programme, status=e.ELIGIBLE)
    h = headers(org)
    body = {
        "programme_id": programme,
        "academic_year": "2026-27",
        "scores": [{"application_id": eligible, "score": 70}],
    }
    made = client.post(f"{BASE}/merit-lists", json=body, headers=h)
    assert made.status_code == 201 and made.json()["entries"][0]["application_id"] == eligible
    merit_id = made.json()["id"]
    assert client.get(f"{BASE}/merit-lists", params={"programme_id": programme}, headers=h).json()[0]["id"] == merit_id
    assert client.get(f"{BASE}/merit-lists/{merit_id}", headers=h).status_code == 200
    assert client.post(f"{BASE}/merit-lists/{merit_id}/publish", headers=h).json()["status"] == "published"
    again = client.post(f"{BASE}/merit-lists/{merit_id}/publish", headers=h)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "merit_list_already_published"

    stranger = {**body, "scores": [{"application_id": new_id(), "score": 1}]}
    refused = client.post(f"{BASE}/merit-lists", json=stranger, headers=h)
    assert refused.status_code == 422 and refused.json()["detail"]["code"] == "score_for_ineligible_application"
    assert client.post(f"{BASE}/merit-lists", json={**body, "programme_id": "x"}, headers=h).status_code == 422
    nan = {**body, "scores": [{"application_id": eligible, "score": "NaN"}]}
    assert client.post(f"{BASE}/merit-lists", json=nan, headers=h).status_code == 422
