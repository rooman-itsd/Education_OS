"""Public routes over HTTP: no token, organisation from /public/{org_slug}/, contract status codes."""

from __future__ import annotations

import pytest
from conftest import BASE, add_application, add_offer, headers, public_slug, seed
from eos_admissions.api.deps import public_organisation
from eos_admissions.api.router import router
from eos_admissions.domain import enums as e
from eos_core.db import new_id
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

APPLICANT = {"first_name": "Ana", "last_name": "Silva", "email": "ana@example.com"}


def submission(**overrides) -> dict:
    return {"applicant": APPLICANT, "programme_id": new_id(), "academic_year": "2026-27"} | overrides


def public(slug: str, path: str = "") -> str:
    return f"{BASE}/public/{slug}/applications{path}"


def test_full_applicant_journey_without_a_token(client, org):
    slug = public_slug(org)
    created = client.post(public(slug), json=submission())
    assert created.status_code == 201
    ref = created.json()["reference_number"]

    tracked = client.get(public(slug, "/track"), params={"reference_number": ref, "email": "ANA@example.com"})
    assert tracked.status_code == 200 and tracked.json()["status"] == "submitted"

    doc = client.post(
        public(slug, f"/{ref}/documents"),
        json={"email": "ana@example.com", "type": "academic_record", "document_id": "doc-1", "label": "Grade 12"},
    )
    assert doc.status_code == 201 and doc.json()["verification_status"] == "pending"

    # Staff take it from submitted to an offer.
    app_id = created.json()["id"]
    staff = headers(org)
    for status in ("under_review", "eligible"):
        client.put(f"{BASE}/applications/{app_id}/status", json={"status": status, "reason": "ok"}, headers=staff)
    assert client.post(f"{BASE}/applications/{app_id}/offer", headers=staff).status_code == 201

    accepted = client.post(public(slug, f"/{ref}/offer/accept"), json={"email": "ana@example.com"})
    assert accepted.status_code == 200 and accepted.json()["status"] == "accepted"


def test_unknown_slug_is_not_found(client):
    response = client.post(public("no-such-org"), json=submission())
    assert response.status_code == 404 and response.json()["detail"]["code"] == "unknown_organisation"
    assert (
        client.get(public("no-such-org", "/track"), params={"reference_number": "x", "email": "a@b.co"}).status_code
        == 404
    )


@pytest.mark.parametrize(
    "body",
    [
        submission(applicant={**APPLICANT, "email": "not-an-email"}),
        submission(applicant={**APPLICANT, "first_name": "   "}),
        submission(applicant={**APPLICANT, "first_name": "x" * 121}),
        submission(programme_id="not-a-uuid"),
        submission(academic_year=""),
        {"applicant": APPLICANT, "academic_year": "2026-27"},
    ],
)
def test_submit_validation(client, org, body):
    assert client.post(public(public_slug(org)), json=body).status_code == 422


def test_wrong_email_answers(client, org):
    slug = public_slug(org)
    ref = client.post(public(slug), json=submission()).json()["reference_number"]
    wrong = "someone.else@example.com"
    assert client.get(public(slug, "/track"), params={"reference_number": ref, "email": wrong}).status_code == 404
    upload = client.post(public(slug, f"/{ref}/documents"), json={"email": wrong, "type": "other", "document_id": "d"})
    assert upload.status_code == 403
    assert client.post(public(slug, f"/{ref}/offer/accept"), json={"email": wrong}).status_code == 403
    assert client.post(public(slug, f"/{ref}/offer/decline"), json={"email": wrong}).status_code == 403


def test_conflicts(client, org):
    slug = public_slug(org)
    closed = seed(add_application, org, status=e.ELIGIBLE, reference_number="ADM-2026-C10SED")
    assert closed
    upload = client.post(
        public(slug, "/ADM-2026-C10SED/documents"),
        json={"email": "ana@example.com", "type": "other", "document_id": "d"},
    )
    assert upload.status_code == 409 and upload.json()["detail"]["code"] == "documents_closed"
    no_offer = client.post(public(slug, "/ADM-2026-C10SED/offer/accept"), json={"email": "ana@example.com"})
    assert no_offer.status_code == 409 and no_offer.json()["detail"]["code"] == "no_open_offer"


def test_decline(client, org):
    slug = public_slug(org)

    def offered(session, organisation_id):
        app = add_application(session, organisation_id, status=e.OFFERED, reference_number="ADM-2026-DEC11E")
        add_offer(session, app)
        return app

    seed(offered, org)
    declined = client.post(
        public(slug, "/ADM-2026-DEC11E/offer/decline"), json={"email": "ana@example.com", "reason": "moved"}
    )
    assert declined.status_code == 200 and declined.json()["offer"]["decline_reason"] == "moved"


def test_one_organisations_slug_never_reaches_another(client):
    org_a, org_b = new_id(), new_id()
    slug_a, slug_b = public_slug(org_a), public_slug(org_b)
    seed(add_application, org_a, reference_number="ADM-2026-5HARED")
    seed(add_application, org_b, reference_number="ADM-2026-5HARED", applicant_email="bo@example.com")
    params = {"reference_number": "ADM-2026-5HARED"}
    assert (
        client.get(public(slug_a, "/track"), params=params | {"email": "ana@example.com"}).json()["organisation_id"]
        == org_a
    )
    assert (
        client.get(public(slug_b, "/track"), params=params | {"email": "bo@example.com"}).json()["organisation_id"]
        == org_b
    )
    assert client.get(public(slug_b, "/track"), params=params | {"email": "ana@example.com"}).status_code == 404


def test_real_dependency_reads_the_organisation_the_gateway_left():
    """Without the test override: the gateway's request.state.organisation_id is used, and its absence is 404."""
    org = new_id()
    application = FastAPI()

    @application.middleware("http")
    async def fake_gateway(request: Request, call_next):
        if "/public/known/" in request.url.path:
            request.state.organisation_id = org
        return await call_next(request)

    application.include_router(router, prefix=BASE)
    assert public_organisation not in application.dependency_overrides
    with TestClient(application) as c:
        made = c.post(public("known"), json=submission())
        assert made.status_code == 201 and made.json()["organisation_id"] == org
        unknown = c.post(public("unknown"), json=submission())
        assert unknown.status_code == 404 and unknown.json()["detail"]["code"] == "unknown_organisation"
