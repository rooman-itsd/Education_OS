"""Every state change writes one audit row; events go to the outbox with exactly the payload fields in
contracts/events.yaml, each carrying organisation_id."""

from __future__ import annotations

import yaml
from conftest import CONTRACTS, add_application, add_document
from eos_admissions.application import service as svc
from eos_admissions.domain import enums as e
from eos_admissions.infrastructure.models import AuditEntry
from eos_core.db import new_id
from eos_core.events import OutboxEvent

PAYLOADS = {
    ev["name"]: set(ev["payload"])
    for ev in yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))["events"]
}


def outbox(db, org) -> list[OutboxEvent]:
    return db.query(OutboxEvent).filter(OutboxEvent.organisation_id == org).order_by(OutboxEvent.occurred_at).all()


def audit(db, org) -> list[AuditEntry]:
    return db.query(AuditEntry).filter(AuditEntry.organisation_id == org).all()


def assert_matches_contract(event: OutboxEvent, org: str, actor: str) -> None:
    assert set(event.payload) == PAYLOADS[event.name], event.name
    assert event.payload["organisation_id"] == org
    assert event.actor == actor


def test_status_change(db, staff, org):
    app = add_application(db, org)
    svc.change_status(db, staff, app.id, e.UNDER_REVIEW, "checking")
    [event] = outbox(db, org)
    assert event.name == "admissions.application.status-changed"
    assert_matches_contract(event, org, staff.user_id)
    assert (event.payload["previous_status"], event.payload["status"], event.payload["reason"]) == (
        e.SUBMITTED,
        e.UNDER_REVIEW,
        "checking",
    )
    [row] = audit(db, org)
    assert (row.action, row.entity, row.entity_id, row.actor) == (
        "status_changed",
        "application",
        app.id,
        staff.user_id,
    )


def test_offer(db, staff, org):
    app = add_application(db, org, status=e.ELIGIBLE)
    view = svc.make_offer(db, staff, app.id)
    [event] = outbox(db, org)
    assert event.name == "admissions.offer.made"
    assert_matches_contract(event, org, staff.user_id)
    assert event.payload["offer_id"] == view["offer"]["id"]
    assert [r.action for r in audit(db, org)] == ["offer_made"]


def test_merit_list_publishes_an_event_only_when_published(db, staff, org):
    merit = svc.generate_merit_list(db, staff, programme_id=new_id(), academic_year="2026-27")
    assert outbox(db, org) == []
    svc.publish_merit_list(db, staff, merit["id"])
    [event] = outbox(db, org)
    assert event.name == "admissions.merit-list.published"
    assert_matches_contract(event, org, staff.user_id)
    assert sorted(r.action for r in audit(db, org)) == ["merit_list_generated", "merit_list_published"]


def test_document_verification_is_audited_without_an_event(db, staff, org):
    doc = add_document(db, add_application(db, org, status=e.UNDER_REVIEW))
    svc.verify_document(db, staff, doc.application_id, doc.id, e.VERIFIED, None)
    assert outbox(db, org) == []
    [row] = audit(db, org)
    assert (row.action, row.entity, row.entity_id) == ("document_verified", "application_document", doc.id)


def test_a_refused_change_writes_nothing(db, staff, org):
    app = add_application(db, org, status=e.REJECTED)
    try:
        svc.change_status(db, staff, app.id, e.UNDER_REVIEW, "r")
    except svc.AdmissionsError:
        pass
    assert outbox(db, org) == [] and audit(db, org) == []
