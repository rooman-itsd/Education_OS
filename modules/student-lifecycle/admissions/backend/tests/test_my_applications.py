"""A signed-in applicant links their application to their account and reads only their own (GET and POST
/me/applications); once linked, admissions.application.accepted carries their user id for fees-accounts."""

from __future__ import annotations

from datetime import timedelta

import pytest
import yaml
from conftest import BASE, CONTRACTS, STAFF, add_application, add_document, add_offer, headers, make_actor, seed
from eos_admissions.application import service as svc
from eos_admissions.application.service import AdmissionsError
from eos_admissions.domain import enums as e
from eos_admissions.infrastructure.models import AuditEntry
from eos_core.db import new_id, utcnow
from eos_core.events import OutboxEvent

APPLICANT = "applicant"
SELF_READ = {"admissions:self:read"}
PAYLOADS = {
    ev["name"]: set(ev["payload"])
    for ev in yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))["events"]
}


def applicant(org: str, user_id: str | None = None):
    return make_actor(org, SELF_READ, user_id=user_id)


def refused(fn, *args) -> tuple[int, str]:
    with pytest.raises(AdmissionsError) as exc:
        fn(*args)
    return exc.value.status, exc.value.code


def accepted_event(db, org) -> OutboxEvent:
    [event] = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.organisation_id == org, OutboxEvent.name == "admissions.application.accepted")
        .all()
    )
    assert set(event.payload) == PAYLOADS[event.name]
    return event


# ---------------------------------------------------------------- service


def test_link_then_list_own_application(db, org):
    app = add_application(db, org)
    add_document(db, app)
    me = applicant(org)
    assert svc.list_my_applications(db, me) == {"items": []}

    linked = svc.link_application(db, me, app.reference_number.lower(), "  ANA@Example.com ")
    assert linked["id"] == app.id and app.applicant_user_id == me.user_id
    [own] = svc.list_my_applications(db, me)["items"]
    assert own["reference_number"] == app.reference_number
    assert [d["verification_status"] for d in own["documents"]] == [e.PENDING]
    assert own["offer"] is None


def test_list_is_only_the_callers_linked_applications_newest_first(db, org):
    me, someone = applicant(org), applicant(org)
    older = add_application(db, org, applicant_user_id=me.user_id, submitted_at=utcnow() - timedelta(days=2))
    newer = add_application(db, org, applicant_user_id=me.user_id)
    add_application(db, org, applicant_user_id=someone.user_id)
    add_application(db, org)  # never linked
    assert [a["id"] for a in svc.list_my_applications(db, me)["items"]] == [newer.id, older.id]


def test_wrong_reference_or_email_reveals_nothing(db, org):
    app = add_application(db, org)
    me = applicant(org)
    assert refused(svc.link_application, db, me, app.reference_number, "someone@example.com") == (404, "not_found")
    assert refused(svc.link_application, db, me, "ADM-0000-XXXXXX", "ana@example.com") == (404, "not_found")
    assert app.applicant_user_id is None


def test_linking_again_is_a_no_op_and_another_account_is_refused(db, org):
    app = add_application(db, org)
    me = applicant(org)
    svc.link_application(db, me, app.reference_number, "ana@example.com")
    svc.link_application(db, me, app.reference_number, "ana@example.com")
    assert refused(svc.link_application, db, applicant(org), app.reference_number, "ana@example.com") == (
        409,
        "already_linked",
    )
    assert app.applicant_user_id == me.user_id
    [row] = db.query(AuditEntry).filter(AuditEntry.organisation_id == org, AuditEntry.entity_id == app.id).all()
    assert (row.action, row.actor) == ("application_linked", me.user_id)


def test_accepted_event_carries_the_linked_user(db, org):
    me = applicant(org)
    app = add_application(db, org, status=e.OFFERED, applicant_user_id=me.user_id)
    add_offer(db, app)
    svc.accept_offer(db, org, app.reference_number, email="ana@example.com")
    assert accepted_event(db, org).payload["user_id"] == me.user_id


def test_accepted_event_has_no_user_when_never_linked(db, org):
    app = add_application(db, org, status=e.OFFERED)
    add_offer(db, app)
    svc.accept_offer(db, org, app.reference_number, email="ana@example.com")
    assert accepted_event(db, org).payload["user_id"] is None


# ---------------------------------------------------------------- HTTP


def test_applicant_links_and_reads_over_http(client, org):
    user = new_id()
    ref = None

    def application(session):
        nonlocal ref
        app = add_application(session, org)
        ref = app.reference_number
        return app

    app_id = seed(application)
    h = headers(org, APPLICANT, user)
    assert client.get(f"{BASE}/me/applications", headers=h).json() == {"items": []}

    linked = client.post(
        f"{BASE}/me/applications", json={"reference_number": ref, "email": "ana@example.com"}, headers=h
    )
    assert linked.status_code == 200 and linked.json()["id"] == app_id
    assert [a["id"] for a in client.get(f"{BASE}/me/applications", headers=h).json()["items"]] == [app_id]

    other = headers(org, APPLICANT, new_id())
    taken = client.post(
        f"{BASE}/me/applications", json={"reference_number": ref, "email": "ana@example.com"}, headers=other
    )
    assert taken.status_code == 409 and taken.json()["detail"]["code"] == "already_linked"
    wrong = client.post(
        f"{BASE}/me/applications", json={"reference_number": ref, "email": "x@example.com"}, headers=other
    )
    assert wrong.status_code == 404


def test_own_routes_need_the_applicant_permission(client, org):
    body = {"reference_number": "ADM-2026-000001", "email": "ana@example.com"}
    assert client.get(f"{BASE}/me/applications").status_code == 401
    for role in (STAFF, "student"):
        assert client.get(f"{BASE}/me/applications", headers=headers(org, role)).status_code == 403
        assert client.post(f"{BASE}/me/applications", json=body, headers=headers(org, role)).status_code == 403


@pytest.mark.parametrize(
    "body",
    [
        {"reference_number": "", "email": "ana@example.com"},
        {"reference_number": "x" * 33, "email": "ana@example.com"},
        {"reference_number": "ADM-2026-000001", "email": "not-an-email"},
        {"email": "ana@example.com"},
    ],
)
def test_link_validation(client, org, body):
    assert client.post(f"{BASE}/me/applications", json=body, headers=headers(org, APPLICANT)).status_code == 422
