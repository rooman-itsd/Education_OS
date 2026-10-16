"""Gate pass (contract 0.2.0, docs/prd.md flow 6): residents apply, wardens approve, security records the
departure and the return."""

from datetime import timedelta

from conftest import NOW, at, events
from eos_core.db import SessionLocal
from eos_hostel.application import jobs, service


def approved_pass(c, me, start: str | None = None, end: str | None = None) -> dict:
    body = {"from": start or at(14), "to": end or at(18), "destination": "Market", "reason": "Shopping"}
    lv = c.post("/me/leave-requests", body, me).json()
    r = c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}, c.warden)
    assert r.status_code == 200, r.text
    return r.json()


def test_security_records_departure_and_return(campus):
    c = campus
    _, security_id_headers = c.org.user("hostel-security")
    person_id, me, _ = c.resident()
    lv = approved_pass(c, me)

    approved = c.get("/leave-requests?status=approved", c.security).json()["items"]
    assert [x["id"] for x in approved] == [lv["id"]]

    r = c.post(f"/leave-requests/{lv['id']}/gate-out", None, c.security)
    assert r.status_code == 200, r.text
    out = r.json()
    assert out["status"] == "out" and out["departed_at"] and out["departure_recorded_by"]
    ev = events("hostel.leave.departed", c.org.id)[-1]
    assert ev == {
        "organisation_id": c.org.id,
        "leave_id": lv["id"],
        "person_id": person_id,
        "hostel_id": c.hostel["id"],
        "departed_at": out["departed_at"],
    }
    assert [x["id"] for x in c.get("/leave-requests?status=out", c.security).json()["items"]] == [lv["id"]]
    assert c.post(f"/leave-requests/{lv['id']}/gate-out", None, c.security).status_code == 409  # already out

    r = c.post(f"/leave-requests/{lv['id']}/gate-in", None, security_id_headers)
    assert r.status_code == 200 and r.json()["status"] == "returned" and r.json()["returned_at"]
    assert r.json()["return_recorded_by"] != out["departure_recorded_by"]  # a second guard on the next shift
    assert events("hostel.leave.returned", c.org.id)[-1]["leave_id"] == lv["id"]
    assert c.post(f"/leave-requests/{lv['id']}/gate-in", None, c.security).status_code == 409  # not out
    assert [x["status"] for x in c.get("/me/leave-requests", me).json()] == ["returned"]


def test_gate_needs_an_approved_pass(campus):
    c = campus
    _, me, _ = c.resident()
    body = {"from": at(14), "to": at(18), "destination": "Home", "reason": "Visit"}
    pending = c.post("/me/leave-requests", body, me).json()
    r = c.post(f"/leave-requests/{pending['id']}/gate-out", None, c.security)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"
    assert c.post(f"/leave-requests/{pending['id']}/gate-in", None, c.security).status_code == 409
    c.post(f"/leave-requests/{pending['id']}/decision", {"decision": "rejected"}, c.warden)
    assert c.post(f"/leave-requests/{pending['id']}/gate-out", None, c.security).status_code == 409


def test_who_may_use_the_gate(campus):
    c = campus
    _, me, _ = c.resident()
    lv = approved_pass(c, me)
    # The resident, the viewer and the hostel office (no hostel:gate:record) cannot record at the gate.
    for headers in (me, c.viewer, c.admin):
        assert c.post(f"/leave-requests/{lv['id']}/gate-out", None, headers).status_code == 403
    # A warden can, for a hostel without a security desk.
    assert c.post(f"/leave-requests/{lv['id']}/gate-out", None, c.warden).json()["status"] == "out"
    assert c.post(f"/leave-requests/{lv['id']}/gate-in", None, me).status_code == 403
    # Security cannot decide, return through the warden's route, or see incidents.
    assert c.post(f"/leave-requests/{lv['id']}/return", None, c.security).status_code == 403
    assert c.get("/incidents", c.security).status_code == 403


def test_warden_marks_return_when_the_gate_did_not(campus):
    c = campus
    _, me, _ = c.resident()
    away = approved_pass(c, me)
    c.post(f"/leave-requests/{away['id']}/gate-out", None, c.security)
    r = c.post(f"/leave-requests/{away['id']}/return", None, c.warden)
    assert r.status_code == 200 and r.json()["status"] == "returned"
    assert r.json()["return_recorded_by"] == c.warden_id
    # Approved but never recorded at the gate: the warden can still close it.
    never_out = approved_pass(c, me, start=at(19), end=at(21))
    assert c.post(f"/leave-requests/{never_out['id']}/return", None, c.warden).json()["status"] == "returned"


def test_out_blocks_withdraw_and_overlapping_leave(campus):
    c = campus
    _, me, _ = c.resident()
    lv = approved_pass(c, me)
    c.post(f"/leave-requests/{lv['id']}/gate-out", None, c.security)
    assert c.post(f"/me/leave-requests/{lv['id']}/withdraw", None, me).status_code == 409
    body = {"from": at(16), "to": at(20), "destination": "Elsewhere", "reason": "x"}
    r = c.post("/me/leave-requests", body, me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "leave_overlaps"


def test_resident_still_out_after_the_end_is_overdue(campus, monkeypatch):
    c = campus
    _, me, _ = c.resident()
    lv = approved_pass(c, me, start=at(8), end=at(10))
    c.post(f"/leave-requests/{lv['id']}/gate-out", None, c.security)
    later = NOW + timedelta(hours=6)
    with SessionLocal() as db:
        jobs.flag_overdue_leave(db, later)
    assert [e["leave_id"] for e in events("hostel.leave.overdue", c.org.id)].count(lv["id"]) == 1
    monkeypatch.setattr(service, "clock", lambda: later)
    listed = c.get("/leave-requests?overdue=true", c.security).json()["items"]
    assert lv["id"] in [x["id"] for x in listed]
    assert c.post(f"/leave-requests/{lv['id']}/gate-in", None, c.security).json()["status"] == "returned"
