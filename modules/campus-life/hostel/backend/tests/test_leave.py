"""Leave and out-passes, including a same-day pass (docs/user-stories.md LV-1..LV-8)."""

from datetime import timedelta

from conftest import NOW, at, events
from eos_core.db import SessionLocal
from eos_hostel.application import jobs, service


def leave(destination: str = "Home", start: str | None = None, end: str | None = None) -> dict:
    return {"from": start or at(14), "to": end or at(18), "destination": destination, "reason": "Family visit"}


def test_day_pass_full_lifecycle(campus):
    c = campus
    person_id, me, _ = c.resident()
    r = c.post("/me/leave-requests", {**leave("Market"), "contact_phone": "+910000000000"}, me)
    assert r.status_code == 201, r.text
    lv = r.json()
    assert lv["status"] == "requested" and lv["hostel_id"] == c.hostel["id"] and lv["person_id"] == person_id
    assert events("hostel.leave.requested", c.org.id)[-1]["leave_id"] == lv["id"]

    pending = c.get("/leave-requests?status=requested", c.warden).json()["items"]
    assert [x["id"] for x in pending] == [lv["id"]]

    r = c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}, c.warden)
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["decided_by"] == c.warden_id
    assert events("hostel.leave.approved", c.org.id)[-1]["decided_by"] == c.warden_id
    assert c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "rejected"}, c.warden).status_code == 409

    r = c.post(f"/leave-requests/{lv['id']}/return", None, c.warden)
    assert r.status_code == 200 and r.json()["status"] == "returned" and r.json()["returned_at"]
    assert events("hostel.leave.returned", c.org.id)[-1]["leave_id"] == lv["id"]
    assert c.post(f"/leave-requests/{lv['id']}/return", None, c.warden).status_code == 409

    mine = c.get("/me/leave-requests", me).json()
    assert [x["status"] for x in mine] == ["returned"]


def test_reject_with_reason(campus):
    c = campus
    _, me, _ = c.resident()
    lv = c.post("/me/leave-requests", leave(), me).json()
    r = c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "rejected", "reason": "Exams tomorrow"}, c.warden)
    assert r.status_code == 200 and r.json()["status"] == "rejected" and r.json()["decision_reason"] == "Exams tomorrow"
    assert events("hostel.leave.rejected", c.org.id)[-1]["leave_id"] == lv["id"]
    assert c.post(f"/leave-requests/{lv['id']}/return", None, c.warden).status_code == 409  # never approved


def test_only_current_residents_apply_and_dates_do_not_overlap(campus):
    c = campus
    _, outsider = c.org.user("hostel-resident")
    r = c.post("/me/leave-requests", leave(), outsider)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_resident"
    _, me, _ = c.resident()
    assert c.post("/me/leave-requests", leave(start=at(18), end=at(14)), me).status_code == 422
    assert c.post("/me/leave-requests", leave(), me).status_code == 201
    r = c.post("/me/leave-requests", leave(start=at(17), end=at(20)), me)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "leave_overlaps"
    assert c.post("/me/leave-requests", leave(start=at(18), end=at(20)), me).status_code == 201  # back to back


def test_withdraw_before_decision_only(campus):
    c = campus
    _, me, _ = c.resident()
    lv = c.post("/me/leave-requests", leave(), me).json()
    _, other_me, _ = c.resident("2")
    assert c.post(f"/me/leave-requests/{lv['id']}/withdraw", None, other_me).status_code == 404
    r = c.post(f"/me/leave-requests/{lv['id']}/withdraw", None, me)
    assert r.status_code == 200 and r.json()["status"] == "withdrawn"
    lv2 = c.post("/me/leave-requests", leave(), me).json()  # withdrawn leave no longer blocks the dates
    c.post(f"/leave-requests/{lv2['id']}/decision", {"decision": "approved"}, c.warden)
    assert c.post(f"/me/leave-requests/{lv2['id']}/withdraw", None, me).status_code == 409


def test_nobody_decides_their_own_leave(campus):
    c = campus
    # A warden who also lives in the hostel and holds the resident role.
    warden_id, both = c.org.user("hostel-warden", "hostel-resident")
    body = {"person_id": warden_id, "room_id": c.room["id"], "bed": "1", "academic_year": "2026-27"}
    alloc = c.post("/allocations", {**body, "from": "2026-10-01", "to": "2027-05-31"}, c.warden).json()
    c.post(f"/allocations/{alloc['id']}/check-in", None, c.warden)
    lv = c.post("/me/leave-requests", leave(), both).json()
    r = c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}, both)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "own_request"


def test_who_may_see_and_decide_leave(campus):
    c = campus
    _, me, _ = c.resident()
    lv = c.post("/me/leave-requests", leave(), me).json()
    for headers in (c.viewer, me):
        assert c.get("/leave-requests", headers).status_code == 403
    assert c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}, me).status_code == 403
    assert c.get("/leave-requests", c.admin).status_code == 200
    # Security sees the passes (hostel:gate:record) but cannot decide them.
    assert c.get("/leave-requests", c.security).status_code == 200
    assert c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}, c.security).status_code == 403


def test_overdue_leave_is_flagged_once_and_listed(campus, monkeypatch):
    c = campus
    _, me, _ = c.resident()
    lv = c.post("/me/leave-requests", leave(start=at(9), end=at(11)), me).json()
    c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}, c.warden)
    later = NOW + timedelta(hours=5)
    with SessionLocal() as db:
        assert jobs.flag_overdue_leave(db, later) >= 1
        assert jobs.flag_overdue_leave(db, later) == 0  # once per leave, never twice
    overdue = [e for e in events("hostel.leave.overdue", c.org.id) if e["leave_id"] == lv["id"]]
    assert len(overdue) == 1 and overdue[0]["hostel_id"] == c.hostel["id"]

    monkeypatch.setattr(service, "clock", lambda: later)
    listed = c.get("/leave-requests?overdue=true", c.warden).json()["items"]
    assert [x["id"] for x in listed] == [lv["id"]]
    assert lv["id"] not in [x["id"] for x in c.get("/leave-requests?overdue=false", c.warden).json()["items"]]
    assert c.post(f"/leave-requests/{lv['id']}/return", None, c.warden).json()["status"] == "returned"


def test_the_security_desk_sees_only_gate_passes(campus):
    """hostel:gate:record lists approved, out and returned leave; pending requests stay with the approvers."""
    c = campus
    _, me, _ = c.resident()
    lv = c.post("/me/leave-requests", leave(), me).json()
    assert c.get("/leave-requests", c.security).json()["items"] == []
    assert c.get("/leave-requests?status=requested", c.security).status_code == 403
    assert [x["id"] for x in c.get("/leave-requests?status=requested", c.warden).json()["items"]] == [lv["id"]]
    c.post(f"/leave-requests/{lv['id']}/decision", {"decision": "approved"}, c.warden)
    assert [x["id"] for x in c.get("/leave-requests", c.security).json()["items"]] == [lv["id"]]
    assert [x["id"] for x in c.get("/leave-requests?status=approved", c.security).json()["items"]] == [lv["id"]]
