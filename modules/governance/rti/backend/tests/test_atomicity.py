"""A change, its audit entry and its event are one transaction: all of them are stored, or none."""

from datetime import date

import pytest
from conftest import APPLICANT, days, outbox
from eos_core.db import SessionLocal, new_id
from eos_rti.application import service as svc
from eos_rti.application.access import Actor
from eos_rti.infrastructure.models import AuditEntry, RtiRequest
from sqlalchemy import select


def actor(org) -> Actor:
    return Actor(user_id=new_id(), organisation_id=org.id, permissions=set())


def session(org):
    """A session scoped to the organisation, as the API's request-scoped session is."""
    db = SessionLocal()
    db.info["organisation_id"] = org.id
    return db


def data() -> dict:
    return {
        "received_via": "post",
        "received_on": date.fromisoformat(days(0)),
        "applicant": dict(APPLICANT),
        "subject": "Atomic records",
        "information_sought": "All of them.",
        "fee": {"status": "exempt"},
    }


def rows(org) -> tuple[int, int, int]:
    """(requests, audit entries, received events) stored for the organisation."""
    with SessionLocal() as db:
        requests = db.scalars(select(RtiRequest).where(RtiRequest.organisation_id == org.id)).all()
        audits = db.scalars(select(AuditEntry).where(AuditEntry.organisation_id == org.id)).all()
    return len(requests), len(audits), len(outbox("rti.request.received", org.id))


def test_the_request_the_audit_entry_and_the_event_are_stored_together(org, clock, settings):
    with session(org) as db:
        svc.create_request(db, actor(org), data())
    assert rows(org) == (1, 1, 1)


def test_if_the_event_cannot_be_written_nothing_is_stored(org, clock, settings, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("the outbox is unavailable")

    monkeypatch.setattr(svc.events, "publish", broken)
    with session(org) as db, pytest.raises(RuntimeError):
        svc.create_request(db, actor(org), data())
    assert rows(org) == (0, 0, 0)


def test_if_the_audit_entry_cannot_be_written_no_event_is_stored(org, clock, settings, monkeypatch):
    def broken(*args, **kwargs):
        raise RuntimeError("the audit table is unavailable")

    monkeypatch.setattr(svc, "_audit", broken)
    with session(org) as db, pytest.raises(RuntimeError):
        svc.create_request(db, actor(org), data())
    assert rows(org) == (0, 0, 0)


def test_closing_publishes_in_the_same_transaction(desk, org, monkeypatch):
    r = desk.request()

    def broken(*args, **kwargs):
        raise RuntimeError("the outbox is unavailable")

    monkeypatch.setattr(svc.events, "publish", broken)
    body = {"authority_name": "Council", "transferred_on": date.fromisoformat(days(0)), "reason": "Wrong body."}
    with session(org) as db, pytest.raises(RuntimeError):
        svc.transfer(db, Actor(user_id=desk.officer_id, organisation_id=org.id), r["id"], body)
    monkeypatch.undo()
    assert desk.ok(desk.get(f"/requests/{r['id']}"))["status"] == "received"  # the status change was rolled back too
    assert outbox("rti.request.closed", org.id) == []
