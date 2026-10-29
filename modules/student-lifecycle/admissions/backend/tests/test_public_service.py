"""Applicant-side use cases: submit, track, attach a document, accept or decline an offer."""

from __future__ import annotations

import re
from datetime import timedelta

import pytest
import yaml
from conftest import CONTRACTS, add_application, add_offer
from eos_admissions.application import service as svc
from eos_admissions.application.service import AdmissionsError
from eos_admissions.domain import enums as e
from eos_admissions.domain import rules
from eos_admissions.infrastructure.models import AuditEntry, Offer
from eos_core.db import new_id, utcnow
from eos_core.events import OutboxEvent

PAYLOADS = {
    ev["name"]: set(ev["payload"])
    for ev in yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))["events"]
}


def refused(fn, *args, **kwargs) -> tuple[int, str]:
    with pytest.raises(AdmissionsError) as exc:
        fn(*args, **kwargs)
    return exc.value.status, exc.value.code


def submit(db, org, **overrides) -> dict:
    values = {
        "first_name": " Ana ",
        "last_name": "Silva",
        "email": "  Ana.Silva@Example.COM ",
        "programme_id": new_id(),
        "academic_year": "2026-27",
    }
    return svc.submit(db, org, **values | overrides)


def only_event(db, org, name: str) -> OutboxEvent:
    [event] = db.query(OutboxEvent).filter(OutboxEvent.organisation_id == org, OutboxEvent.name == name).all()
    assert set(event.payload) == PAYLOADS[name]
    assert event.payload["organisation_id"] == org
    return event


# ---------------------------------------------------------------- submit


def test_submit(db, org):
    app = submit(db, org)
    assert re.fullmatch(r"ADM-\d{4}-[0-9A-F]{6}", app["reference_number"])
    assert app["status"] == e.SUBMITTED and app["organisation_id"] == org
    assert app["applicant"]["email"] == "ana.silva@example.com"
    assert app["applicant"]["first_name"] == "Ana"
    assert app["documents"] == [] and app["offer"] is None
    event = only_event(db, org, "admissions.application.submitted")
    assert event.actor == app["id"]
    assert event.payload["applicant_email"] == "ana.silva@example.com"
    [audit] = db.query(AuditEntry).filter(AuditEntry.organisation_id == org).all()
    assert (audit.action, audit.actor) == ("submitted", app["id"])


def test_reference_prefix_from_config(db, org, monkeypatch):
    monkeypatch.setenv("ADMISSIONS_REFERENCE_PREFIX", "APP")
    assert submit(db, org)["reference_number"].startswith("APP-")


def test_reference_collision_is_retried(db, org, monkeypatch):
    taken = add_application(db, org, reference_number="ADM-2026-AAAAAA")
    numbers = iter([taken.reference_number, "ADM-2026-BBBBBB"])
    monkeypatch.setattr(rules, "generate_reference_number", lambda prefix: next(numbers))
    assert submit(db, org)["reference_number"] == "ADM-2026-BBBBBB"


def test_reference_gives_up_after_the_configured_attempts(db, org, monkeypatch):
    add_application(db, org, reference_number="ADM-2026-AAAAAA")
    monkeypatch.setenv("ADMISSIONS_REFERENCE_COLLISION_RETRIES", "2")
    monkeypatch.setattr(rules, "generate_reference_number", lambda prefix: "ADM-2026-AAAAAA")
    assert refused(submit, db, org) == (503, "reference_unavailable")


def test_the_same_reference_may_exist_in_two_organisations(db, org, other_org, monkeypatch):
    monkeypatch.setattr(rules, "generate_reference_number", lambda prefix: "ADM-2026-CCCCCC")
    assert submit(db, org)["reference_number"] == submit(db, other_org)["reference_number"]


# ---------------------------------------------------------------- track


def test_track_needs_reference_and_email(db, org, other_org):
    app = submit(db, org)
    ref = app["reference_number"]
    assert svc.track(db, org, ref, "ANA.SILVA@example.com")["id"] == app["id"]
    assert svc.track(db, org, f" {ref.lower()} ", "ana.silva@example.com")["id"] == app["id"]
    assert refused(svc.track, db, org, ref, "someone@example.com") == (404, "not_found")
    assert refused(svc.track, db, org, "ADM-2026-000000", "ana.silva@example.com") == (404, "not_found")
    assert refused(svc.track, db, other_org, ref, "ana.silva@example.com") == (404, "not_found")


# ---------------------------------------------------------------- documents


def test_attach_document(db, org):
    app = submit(db, org)
    doc = svc.attach_document(
        db, org, app["reference_number"], email="ana.silva@example.com", type="identity_proof", document_id="doc-77"
    )
    assert doc["verification_status"] == e.PENDING and doc["application_id"] == app["id"]
    assert [d["id"] for d in svc.track(db, org, app["reference_number"], "ana.silva@example.com")["documents"]] == [
        doc["id"]
    ]
    actions = [a.action for a in db.query(AuditEntry).filter(AuditEntry.organisation_id == org)]
    assert sorted(actions) == ["document_attached", "submitted"]


def test_attach_document_refusals(db, org):
    app = submit(db, org)
    ref = app["reference_number"]
    kwargs = {"type": "other", "document_id": "d"}
    assert refused(svc.attach_document, db, org, ref, email="x@example.com", **kwargs) == (403, "email_mismatch")
    assert refused(svc.attach_document, db, org, "ADM-2026-000000", email="ana.silva@example.com", **kwargs) == (
        404,
        "not_found",
    )
    closed = add_application(db, org, status=e.ELIGIBLE, applicant_email="ana.silva@example.com")
    assert refused(svc.attach_document, db, org, closed.reference_number, email="ana.silva@example.com", **kwargs) == (
        409,
        "documents_closed",
    )


# ---------------------------------------------------------------- offers


def offered(db, org, **offer_overrides):
    app = add_application(db, org, status=e.OFFERED)
    offer = add_offer(db, app, **offer_overrides)
    return app, offer


def test_accept_offer(db, org):
    app, offer = offered(db, org, expires_at=utcnow() + timedelta(days=7))
    view = svc.accept_offer(db, org, app.reference_number, email="ANA@example.com")
    assert view["status"] == e.ACCEPTED and view["decided_at"] is not None
    assert view["offer"]["status"] == e.ACCEPTED
    event = only_event(db, org, "admissions.application.accepted")
    assert event.actor == app.id
    assert (event.payload["applicant_first_name"], event.payload["programme_id"]) == ("Ana", app.programme_id)
    assert refused(svc.accept_offer, db, org, app.reference_number, email="ana@example.com") == (409, "no_open_offer")
    assert refused(svc.decline_offer, db, org, app.reference_number, email="ana@example.com") == (409, "no_open_offer")


def test_decline_offer(db, org):
    app, offer = offered(db, org)
    view = svc.decline_offer(db, org, app.reference_number, email="ana@example.com", reason="  chose another  ")
    assert view["status"] == e.DECLINED
    db.refresh(offer)
    assert (offer.status, offer.decline_reason) == (e.DECLINED, "chose another")
    assert only_event(db, org, "admissions.application.declined").payload["reason"] == "chose another"


def test_decline_without_reason_sends_an_empty_reason(db, org):
    app, offer = offered(db, org)
    svc.decline_offer(db, org, app.reference_number, email="ana@example.com")
    db.refresh(offer)
    assert offer.decline_reason is None
    assert only_event(db, org, "admissions.application.declined").payload["reason"] == ""


def test_offer_decision_refusals(db, org):
    app, _ = offered(db, org)
    assert refused(svc.accept_offer, db, org, app.reference_number, email="x@example.com") == (403, "email_mismatch")
    assert refused(svc.accept_offer, db, org, "ADM-2026-000000", email="ana@example.com") == (404, "not_found")

    expired, _ = offered(db, org, expires_at=utcnow() - timedelta(minutes=1))
    assert refused(svc.accept_offer, db, org, expired.reference_number, email="ana@example.com") == (
        409,
        "no_open_offer",
    )

    never_offered = add_application(db, org, status=e.ELIGIBLE)
    assert refused(svc.decline_offer, db, org, never_offered.reference_number, email="ana@example.com") == (
        409,
        "no_open_offer",
    )


def test_staff_withdrawal_closes_the_offer_for_the_applicant(db, org, staff):
    app, _ = offered(db, org)
    svc.change_status(db, staff, app.id, e.WITHDRAWN, "missed deadline")
    assert refused(svc.accept_offer, db, org, app.reference_number, email="ana@example.com") == (409, "no_open_offer")
    assert db.query(Offer).filter(Offer.application_id == app.id, Offer.status == e.OFFER_OPEN).count() == 0
