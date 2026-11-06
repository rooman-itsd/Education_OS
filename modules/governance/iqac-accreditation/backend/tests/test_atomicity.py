"""State, audit entry and event are written in one transaction: if the event cannot be written, nothing is."""

import pytest
from conftest import audit, outbox
from eos_core import events
from eos_core.db import SessionLocal
from eos_iqac_accreditation.infrastructure.models import AuditEntry
from sqlalchemy import func, select


def failing_publish(monkeypatch):
    """The event is staged in the session and then the request fails before the commit."""
    real = events.publish

    def publish_then_fail(*args, **kwargs):
        real(*args, **kwargs)
        raise RuntimeError("the outbox write failed")

    monkeypatch.setattr(events, "publish", publish_then_fail)


def audit_count(org_id: str) -> int:
    with SessionLocal() as db:
        return db.scalar(select(func.count()).select_from(AuditEntry).where(AuditEntry.organisation_id == org_id))


def test_a_cycle_status_change_and_its_event_and_audit_entry_land_together(desk):
    d = desk
    c = d.cycle()
    before = audit_count(d.org.id)
    d.move(c["id"], "collecting")
    assert audit_count(d.org.id) == before + 1
    assert len(outbox("iqac-accreditation.cycle.status-changed", d.org.id)) == 1


def test_a_failed_event_write_rolls_back_the_status_the_audit_entry_and_the_event(desk, monkeypatch):
    d = desk
    c = d.cycle()
    before = audit_count(d.org.id)
    failing_publish(monkeypatch)
    with pytest.raises(RuntimeError):
        d.post(f"/cycles/{c['id']}/status", {"status": "collecting"})
    monkeypatch.undo()
    assert d.ok(d.get(f"/cycles/{c['id']}"))["status"] == "planning"
    assert audit_count(d.org.id) == before
    assert audit(d.org.id, c["id"]) == [("cycle.created", None)]
    assert outbox("iqac-accreditation.cycle.status-changed", d.org.id) == []


def test_a_failed_event_write_leaves_a_response_submitted(desk, monkeypatch):
    d = desk
    c = d.submitted_q()
    rid = c["q"]["id"]
    before = audit_count(d.org.id)
    failing_publish(monkeypatch)
    with pytest.raises(RuntimeError):
        d.post(f"/responses/{rid}/review", {"decision": "accept"})
    monkeypatch.undo()
    r = d.ok(d.get(f"/responses/{rid}"))
    assert (r["status"], r["reviewed_by"], r["reviewed_at"]) == ("submitted", None, None)
    assert audit_count(d.org.id) == before
    assert outbox("iqac-accreditation.response.accepted", d.org.id) == []
    # The same request succeeds once the outbox works, with all three written.
    d.ok(d.post(f"/responses/{rid}/review", {"decision": "accept"}))
    assert audit(d.org.id, rid)[-1] == ("response.accepted", None)
    assert len(outbox("iqac-accreditation.response.accepted", d.org.id)) == 1


def test_a_return_publishes_nothing_but_is_audited(desk):
    d = desk
    c = d.submitted_q()
    d.ok(d.post(f"/responses/{c['q']['id']}/review", {"decision": "return", "comment": "More detail"}))
    assert outbox("iqac-accreditation.response.accepted", d.org.id) == []
    assert audit(d.org.id, c["q"]["id"])[-1] == ("response.returned", "More detail")


def test_every_state_change_writes_an_audit_entry(desk):
    d = desk
    before = audit_count(d.org.id)
    f = d.framework()
    m = d.metric(f["id"])
    c = d.cycle(f["id"])
    d.ok(d.patch(f"/cycles/{c['id']}", {"name": "x"}))
    d.move(c["id"], "collecting")
    r = d.assign(c["id"], (m["id"], d.alice_id, "2026-12-01"))[0]
    d.ok(d.put(f"/responses/{r['id']}", {"value": 1}, d.alice))
    e = d.ok(d.post(f"/responses/{r['id']}/evidence", {"title": "x", "kind": "link", "url": "https://e.edu"}, d.alice))
    d.ok(d.delete(f"/responses/{r['id']}/evidence/{e['id']}", d.alice))
    d.ok(d.post(f"/responses/{r['id']}/submit", None, d.alice))
    d.ok(d.post(f"/responses/{r['id']}/review", {"decision": "accept"}))
    i = d.action_item()
    d.ok(d.patch(f"/action-items/{i['id']}", {"title": "y"}))
    d.ok(d.patch(f"/action-items/{i['id']}", {"status": "in_progress"}))
    d.ok(d.patch(f"/frameworks/{f['id']}", {"name": "z"}))
    d.ok(d.patch(f"/metrics/{m['id']}", {"title": "z"}))
    # framework 2, metric 2, cycle 3, response 4, evidence 2, action item 3: 16 changes, 16 entries.
    assert audit_count(d.org.id) - before == 16
    # Reads write nothing.
    d.ok(d.get("/frameworks"))
    d.ok(d.get("/stats/action-items"))
    assert audit_count(d.org.id) - before == 16


def test_audit_entries_hold_no_values_narratives_or_links(desk):
    d = desk
    c = d.collecting()
    d.ok(d.put(f"/responses/{c['q']['id']}", {"value": 98765.4321, "narrative": "secret narrative"}, d.alice))
    d.ok(
        d.post(
            f"/responses/{c['q']['id']}/evidence",
            {"title": "t", "kind": "link", "url": "https://secret.example/x", "note": "secret note"},
            d.alice,
        )
    )
    with SessionLocal() as db:
        rows = db.scalars(select(AuditEntry).where(AuditEntry.organisation_id == d.org.id)).all()
    text = " ".join(f"{r.action} {r.entity} {r.reason}" for r in rows)
    for secret in ("98765", "secret", "narrative"):
        assert secret not in text
