"""Module standard rule 11: one organisation never reads or changes another's rows."""

from __future__ import annotations

from conftest import BASE, add_enrolment, add_offering, add_section, add_window, headers, mint_token, seed
from eos_core.db import new_id
from eos_enrolment_registration.application import service as svc
from eos_testing import assert_no_cross_tenant_leak


def token(org: str) -> str:
    return mint_token(org, ["registration-staff"])


def test_no_cross_tenant_leak_on_lists(client):
    org_a, org_b, term = new_id(), new_id(), new_id()
    for org in (org_a, org_b):
        seed(add_window, org, term)
        for _ in range(2):
            student = seed(add_enrolment, org)
            client.post(
                f"{BASE}/registrations",
                json={
                    "programme_enrolment_id": student.id,
                    "course_offering_id": new_id(),
                    "section_id": new_id(),
                    "academic_period_id": term,
                },
                headers=headers(org),
            )
    assert_no_cross_tenant_leak(client, f"{BASE}/programme-enrolments", token(org_a), token(org_b))
    assert_no_cross_tenant_leak(client, f"{BASE}/registrations", token(org_a), token(org_b))
    report_a = client.get(f"{BASE}/reports/registered-candidates", headers=headers(org_a)).json()
    assert report_a["total"] == 2


def test_another_organisation_cannot_touch_anything_by_id(client):
    org_a, org_b, term = new_id(), new_id(), new_id()
    seed(add_window, org_a, term)
    student = seed(add_enrolment, org_a)
    reg = client.post(
        f"{BASE}/registrations",
        json={
            "programme_enrolment_id": student.id,
            "course_offering_id": new_id(),
            "section_id": new_id(),
            "academic_period_id": term,
        },
        headers=headers(org_a),
    ).json()
    h = headers(org_b)
    attempts = [
        client.get(f"{BASE}/programme-enrolments/{student.id}", headers=h),
        client.post(f"{BASE}/programme-enrolments/{student.id}/withdraw", json={"reason": "x"}, headers=h),
        client.post(f"{BASE}/programme-enrolments/{student.id}/complete", headers=h),
        client.get(f"{BASE}/terms/{term}/registration-window", headers=h),
        client.get(f"{BASE}/registrations/{reg['id']}", headers=h),
        client.post(f"{BASE}/registrations/{reg['id']}/withdraw", json={"reason": "x"}, headers=h),
        client.post(
            f"{BASE}/registrations/{reg['id']}/change-section",
            json={"to_section_id": new_id(), "effective_on": "2026-11-02"},
            headers=h,
        ),
        client.post(
            f"{BASE}/registrations",
            json={
                "programme_enrolment_id": student.id,
                "course_offering_id": new_id(),
                "section_id": new_id(),
                "academic_period_id": term,
            },
            headers=h,
        ),
    ]
    assert [r.status_code for r in attempts] == [404] * len(attempts)
    bulk = client.post(
        f"{BASE}/registrations/bulk",
        json={
            "programme_enrolment_ids": [student.id],
            "course_offering_id": new_id(),
            "section_id": new_id(),
            "academic_period_id": term,
        },
        headers=h,
    ).json()
    assert bulk["results"][0]["code"] == "not_found"
    owner = client.get(f"{BASE}/registrations/{reg['id']}", headers=headers(org_a)).json()
    assert owner["status"] == "confirmed"


def test_another_organisations_local_copies_never_affect_checks(db, org, other_org):
    from conftest import make_actor

    term = new_id()
    add_window(db, org, term)
    closed_elsewhere = add_offering(db, other_org, term, status="cancelled")
    full_elsewhere = add_section(db, closed_elsewhere, capacity=0)
    reg = svc.register(
        db,
        make_actor(org),
        programme_enrolment_id=add_enrolment(db, org).id,
        course_offering_id=closed_elsewhere.course_offering_id,
        section_id=full_elsewhere.section_id,
        academic_period_id=term,
    )
    assert reg["status"] == "confirmed" and reg["references_verified"] is False
