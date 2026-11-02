"""Module standard rule 11: one organisation never reads or changes another's rows."""

from __future__ import annotations

from conftest import BASE, add_application, add_document, headers, mint_token, seed
from eos_admissions.domain import enums as e
from eos_core.db import new_id
from eos_testing import assert_no_cross_tenant_leak


def token(org: str) -> str:
    return mint_token(org, ["admissions-staff"])


def test_no_cross_tenant_leak_on_lists(client):
    org_a, org_b = new_id(), new_id()
    for org in (org_a, org_b):
        seed(add_application, org)
        seed(add_application, org, status=e.ELIGIBLE)
        client.post(
            f"{BASE}/merit-lists",
            json={"programme_id": new_id(), "academic_year": "2026-27"},
            headers=headers(org),
        )
    assert_no_cross_tenant_leak(client, f"{BASE}/applications", token(org_a), token(org_b))
    assert_no_cross_tenant_leak(client, f"{BASE}/merit-lists", token(org_a), token(org_b))


def test_document_queue_and_funnel_stay_inside_the_organisation(client):
    """Queue rows carry no organisation_id in the contract, so compare ids instead of using the shared helper."""
    org_a, org_b = new_id(), new_id()

    def documents_for(session, organisation_id, count):
        app = add_application(session, organisation_id, status=e.UNDER_REVIEW)
        for _ in range(count):
            add_document(session, app)
        return app

    seed(documents_for, org_a, 2)
    seed(documents_for, org_b, 3)
    queue_a = client.get(f"{BASE}/documents", headers=headers(org_a)).json()
    queue_b = client.get(f"{BASE}/documents", headers=headers(org_b)).json()
    assert (queue_a["total"], queue_b["total"]) == (2, 3)
    assert not {d["id"] for d in queue_a["items"]} & {d["id"] for d in queue_b["items"]}

    funnel_a = client.get(f"{BASE}/reports/funnel", headers=headers(org_a)).json()
    funnel_b = client.get(f"{BASE}/reports/funnel", headers=headers(org_b)).json()
    assert (funnel_a["total"], funnel_b["total"]) == (1, 1)


def test_another_organisation_cannot_touch_anything_by_id(client):
    org_a, org_b = new_id(), new_id()
    app_id = seed(add_application, org_a, status=e.ELIGIBLE)

    def doc_on(session, application_id):
        from eos_admissions.infrastructure.models import Application

        return add_document(session, session.get(Application, application_id))

    doc_id = seed(doc_on, app_id)
    merit = client.post(
        f"{BASE}/merit-lists", json={"programme_id": new_id(), "academic_year": "2026-27"}, headers=headers(org_a)
    ).json()
    h = headers(org_b)
    attempts = [
        client.get(f"{BASE}/applications/{app_id}", headers=h),
        client.put(f"{BASE}/applications/{app_id}/status", json={"status": "withdrawn", "reason": "x"}, headers=h),
        client.post(
            f"{BASE}/applications/{app_id}/documents/{doc_id}/verify",
            json={"verification_status": "verified"},
            headers=h,
        ),
        client.post(f"{BASE}/applications/{app_id}/offer", headers=h),
        client.get(f"{BASE}/merit-lists/{merit['id']}", headers=h),
        client.post(f"{BASE}/merit-lists/{merit['id']}/publish", headers=h),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)

    owner = client.get(f"{BASE}/applications/{app_id}", headers=headers(org_a)).json()
    assert owner["status"] == e.ELIGIBLE and owner["offer"] is None
    assert owner["documents"][0]["verification_status"] == e.PENDING
    assert client.get(f"{BASE}/merit-lists/{merit['id']}", headers=headers(org_a)).json()["status"] == e.DRAFT


def test_an_applicant_never_links_or_reads_another_organisations_application(client):
    """The same user id, reference number and email in two organisations: each token sees only its own."""
    org_a, org_b = new_id(), new_id()
    user = new_id()
    reference = f"ADM-2026-{new_id()[:6].upper()}"
    app_a = seed(add_application, org_a, reference_number=reference, applicant_user_id=user)
    app_b = seed(add_application, org_b, reference_number=reference)

    as_a, as_b = headers(org_a, "applicant", user), headers(org_b, "applicant", user)
    assert [a["id"] for a in client.get(f"{BASE}/me/applications", headers=as_a).json()["items"]] == [app_a]
    assert client.get(f"{BASE}/me/applications", headers=as_b).json() == {"items": []}

    # Linking from org B reaches org B's application only, never org A's already-linked one.
    body = {"reference_number": reference, "email": "ana@example.com"}
    linked = client.post(f"{BASE}/me/applications", json=body, headers=as_b)
    assert linked.status_code == 200 and linked.json()["id"] == app_b
    assert (
        client.post(f"{BASE}/me/applications", json=body, headers=headers(new_id(), "applicant", user)).status_code
        == 404
    )
