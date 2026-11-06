"""A state change is all or nothing: a failure at any step leaves no case, audit entry or event behind, and the audit
entry and the event are written in the same transaction as the change."""

import pytest
from conftest import DESCRIPTION, Campus
from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_grievance.application import service
from eos_grievance.application.access import Actor
from eos_grievance.infrastructure.models import AuditEntry, Grievance
from sqlalchemy import func, select


class InjectedError(RuntimeError):
    pass


def session_for(org):
    db = SessionLocal()
    db.info["organisation_id"] = org.id
    return db


def counts(org) -> tuple[int, int, int]:
    with SessionLocal() as db:
        cases = db.scalar(select(func.count()).select_from(Grievance).where(Grievance.organisation_id == org.id))
        audits = db.scalar(select(func.count()).select_from(AuditEntry).where(AuditEntry.organisation_id == org.id))
        events = db.scalar(select(func.count()).select_from(OutboxEvent).where(OutboxEvent.organisation_id == org.id))
    return cases, audits, events


def actor(org, user_id: str, *permissions: str) -> Actor:
    return Actor(user_id=user_id, organisation_id=org.id, permissions=set(permissions))


def fail(*args, **kwargs):
    raise InjectedError("store down")


FILE = {"track": "student_grievance", "category": "x", "description": DESCRIPTION}


def test_a_failing_event_rolls_back_the_case_and_its_audit_entry(campus, monkeypatch):
    c = campus
    monkeypatch.setattr(service, "_publish", fail)
    before = counts(c.org)
    with session_for(c.org) as db, pytest.raises(InjectedError):
        service.file_case(db, actor(c.org, c.complainant_id, "grievance:case:file"), FILE)
    assert counts(c.org) == before


def test_a_failing_audit_rolls_back_the_case_and_its_event(campus, monkeypatch):
    c = campus
    monkeypatch.setattr(service, "_audit", fail)
    before = counts(c.org)
    with session_for(c.org) as db, pytest.raises(InjectedError):
        service.file_case(db, actor(c.org, c.complainant_id, "grievance:case:file"), FILE)
    assert counts(c.org) == before


def test_a_failing_audit_keeps_the_case_as_it_was_and_publishes_nothing(campus, monkeypatch):
    c = campus
    case = c.file()
    before = counts(c.org)
    monkeypatch.setattr(service, "_audit", fail)
    me = actor(c.org, c.complainant_id, "grievance:case:read-own")
    with session_for(c.org) as db, pytest.raises(InjectedError):
        service.withdraw_case(db, me, case["id"], "reason")
    assert counts(c.org) == before
    assert c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))["status"] == "submitted"


def test_a_failing_event_keeps_the_case_open_when_it_is_not_admitted(campus, monkeypatch):
    c = campus
    case = c.file()
    before = counts(c.org)
    monkeypatch.setattr(service, "_publish", fail)
    member = actor(c.org, c.members["sgrc"][0], "grievance:case:manage")
    with session_for(c.org) as db, pytest.raises(InjectedError):
        service.move_case(db, member, case["id"], "not_admitted", "Outside the remit.")
    assert counts(c.org) == before
    assert c.ok(c.get(f"/grievances/{case['id']}", c.member()))["status"] == "submitted"


def test_events_and_audit_entries_belong_to_the_changed_rows_organisation(campus):
    c = campus
    case = c.file()
    with SessionLocal() as db:
        events = list(db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == c.org.id)))
        audits = list(db.scalars(select(AuditEntry).where(AuditEntry.entity_id == case["id"])))
    assert {e.organisation_id for e in events} == {c.org.id}
    assert {e.payload["organisation_id"] for e in events if e.name.startswith("grievance.")} == {c.org.id}
    assert {a.organisation_id for a in audits} == {c.org.id} and audits


def test_notices_go_out_only_after_the_commit(campus, monkeypatch):
    from eos_grievance.infrastructure import notifier

    c = campus
    notifier.sent.clear()
    monkeypatch.setattr(service, "_audit", fail)
    with session_for(c.org) as db, pytest.raises(InjectedError):
        service.file_case(db, actor(c.org, c.complainant_id, "grievance:case:file"), FILE)
    assert notifier.sent == []


def test_a_failed_filing_does_not_use_up_a_case_number(campus, monkeypatch):
    c = campus
    first = c.file()
    monkeypatch.setattr(service, "_publish", fail)
    with session_for(c.org) as db, pytest.raises(InjectedError):
        service.file_case(db, actor(c.org, c.complainant_id, "grievance:case:file"), FILE)
    monkeypatch.undo()
    assert first["number"] == "GRV-000001" and c.file()["number"] == "GRV-000002"
    assert new_id() and Campus
