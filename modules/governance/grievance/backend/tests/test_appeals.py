"""SGRC appeals to the ombudsperson committee and the appeal window (docs/prd.md "Main flows" 8 and 10)."""

from datetime import datetime, timedelta

from conftest import audit, outbox
from eos_grievance.infrastructure import notifier

REASON = "The findings ignore the receipts I provided."


def appeal(c, case_id, headers=None):
    return c.post(f"/me/grievances/{case_id}/appeal", {"reason": REASON}, headers or c.complainant)


def test_without_an_appeal_window_no_appeal_is_accepted(campus):
    c = campus
    case = c.file()
    decided = c.decide(case["id"])
    mine = c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))
    assert mine["can_appeal"] is False
    r = appeal(c, case["id"])
    assert r.status_code == 409
    assert r.json()["detail"] == {"code": "appeal_window_not_configured", "message": "Appeal window is not configured"}
    # nothing can be appealed, so the decided case closes at once
    assert c.move(case["id"], "closed")["status"] == "closed"
    assert decided["status"] == "decided"


def test_the_full_appeal_path(campus, monkeypatch, clock):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    case = c.file()
    c.decide(case["id"])
    mine = c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))
    assert mine["can_appeal"] is True and mine["decision"]["outcome"] == "upheld"
    notifier.sent.clear()
    clock.advance(days=3)
    appealed = c.ok(appeal(c, case["id"]))
    assert appealed["status"] == "appealed" and appealed["can_appeal"] is False
    assert [n["person_id"] for n in notifier.sent] == [c.members["ombudsperson"][0]]
    # from now on the ombudsperson committee handles it; the SGRC still reads it but cannot change it
    ombud = c.ok(c.get(f"/grievances/{case['id']}", c.member("ombudsperson")))
    assert ombud["appeal"]["committee_id"] == c.committees["ombudsperson"]["id"] and ombud["appeal"]["outcome"] is None
    assert c.get(f"/grievances/{case['id']}", c.member("sgrc")).status_code == 200
    r = c.post(f"/grievances/{case['id']}/updates", {"body": "hello"}, c.member("sgrc"))
    assert r.status_code == 403
    assert c.post(f"/grievances/{case['id']}/updates", {"body": "hello"}, c.member("ombudsperson")).status_code == 201
    r = c.post(f"/grievances/{case['id']}/status", {"status": "closed"}, c.member("ombudsperson"))
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "invalid_status")
    # decide the appeal
    notifier.sent.clear()
    body = {"outcome": "modified", "outcome_note": "The sanction is reduced."}
    detail = c.ok(c.post(f"/grievances/{case['id']}/appeal-decision", body, c.member("ombudsperson")))
    assert detail["status"] == "appeal_decided"
    assert detail["appeal"]["outcome"] == "modified" and detail["appeal"]["decided_by"] == c.members["ombudsperson"][0]
    assert [n["person_id"] for n in notifier.sent] == [c.complainant_id]
    mine = c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))
    assert mine["appeal"]["outcome_note"] == "The sanction is reduced."
    closed = c.move(case["id"], "closed", "ombudsperson")
    assert closed["closure"] == "decided"
    (event,) = outbox("grievance.case.closed", c.org.id)
    assert event["appealed"] is True and event["committee_id"] == c.committees["sgrc"]["id"]
    actions = [a for a, _ in audit(c.org.id, case["id"])]
    assert "case.appealed" in actions and "appeal.decided" in actions


def test_the_window_closes_and_the_case_closes_after_it(campus, monkeypatch, clock):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    case = c.file()
    c.decide(case["id"])
    r = c.post(f"/grievances/{case['id']}/status", {"status": "closed"}, c.member())
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "appeal_window_open")
    clock.advance(days=7, hours=1)
    r = appeal(c, case["id"])
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "appeal_window_passed")
    assert c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))["can_appeal"] is False
    assert c.move(case["id"], "closed")["status"] == "closed"


def test_the_last_instant_of_the_window_still_counts(campus, monkeypatch, clock):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    case = c.file()
    decided = c.decide(case["id"])
    clock.set(datetime.fromisoformat(decided["decided_at"]) + timedelta(days=7))
    assert c.ok(appeal(c, case["id"]))["status"] == "appealed"


def test_only_decided_student_grievances_can_be_appealed(campus, monkeypatch):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    fresh = c.file()
    r = appeal(c, fresh["id"])
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "invalid_status")
    ragging = c.file("ragging")
    c.decide(ragging["id"], "anti_ragging")
    r = appeal(c, ragging["id"])
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "appeal_not_allowed")
    assert c.ok(c.get(f"/me/grievances/{ragging['id']}", c.complainant))["can_appeal"] is False
    assert c.post(f"/me/grievances/{fresh['id']}/appeal", {"reason": "short"}, c.complainant).status_code == 422
    c.decide(fresh["id"])
    assert appeal(c, fresh["id"]).status_code == 200
    again = appeal(c, fresh["id"])
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "invalid_status")


def test_an_appeal_needs_an_active_ombudsperson_committee(campus, monkeypatch):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    c.ok(c.patch(f"/committees/{c.committees['ombudsperson']['id']}", {"active": False}))
    case = c.file()
    c.decide(case["id"])
    r = appeal(c, case["id"])
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "no_ombudsperson")


def test_appeal_decisions_are_for_the_ombudsperson_of_an_appealed_case(campus, monkeypatch):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "7")
    case = c.file()
    c.decide(case["id"])
    body = {"outcome": "dismissed", "outcome_note": "No grounds."}
    path = f"/grievances/{case['id']}/appeal-decision"
    r = c.post(path, body, c.member("sgrc"))
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_appealed")
    assert c.post(path, body, c.member("ombudsperson")).status_code == 404  # not appealed to them yet: no access
    c.ok(appeal(c, case["id"]))
    assert (
        c.post(path, body, c.member("sgrc")).status_code == 403
    )  # the SGRC member holds appeal:decide but sits on the wrong committee
    assert c.post(path, body, c.complainant).status_code == 403
    for bad in (
        {"outcome": "upheld"},
        {"outcome": "wrong", "outcome_note": "abc"},
        {"outcome": "upheld", "outcome_note": "ab"},
    ):
        assert c.post(path, bad, c.member("ombudsperson")).status_code == 422
    assert c.post(path, body, c.member("ombudsperson")).status_code == 200
    r = c.post(path, body, c.member("ombudsperson"))
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "not_appealed")


def test_working_days_skip_weekends(campus, monkeypatch, clock):
    c = campus
    monkeypatch.setenv("GRIEVANCE_APPEAL_WINDOW_DAYS", "2")
    monkeypatch.setenv("GRIEVANCE_DAY_COUNTING", "working")
    case = c.file()
    decided = c.decide(case["id"])  # decided on Thursday 5 November
    clock.set(datetime.fromisoformat(decided["decided_at"]) + timedelta(days=4))  # Monday: the second working day
    assert c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))["can_appeal"] is True
    clock.advance(seconds=1)  # one second later it is past
    assert c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))["can_appeal"] is False
