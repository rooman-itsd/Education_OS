"""What committee members do with a case: admit, inquire, record proceedings, message, decide, transfer, close
(docs/prd.md "Main flows" 3 to 10)."""

from conftest import audit, outbox
from eos_core.db import new_id
from eos_grievance.infrastructure import notifier


def test_the_normal_path_from_filing_to_closing_a_ragging_case(campus):
    c = campus
    case = c.file("ragging")
    path = f"/grievances/{case['id']}"
    acknowledged = c.move(case["id"], "acknowledged", "anti_ragging")
    assert acknowledged["status"] == "acknowledged" and acknowledged["acknowledged_at"]
    c.move(case["id"], "under_inquiry", "anti_ragging")
    proceeding = {"kind": "statement", "held_on": "2026-11-03", "summary": "Statement of the complainant."}
    p = c.ok(c.post(f"{path}/proceedings", proceeding, c.member("anti_ragging")))
    assert p["recorded_by"] == c.members["anti_ragging"][0] and p["kind"] == "statement"
    decision = {
        "outcome": "partly_upheld",
        "findings": "The senior students were warned.",
        "actions_recommended": "A written warning.",
    }
    detail = c.ok(c.post(f"{path}/decision", decision, c.member("anti_ragging")))
    assert detail["status"] == "decided" and detail["decided_at"]
    assert (
        detail["decision"]["outcome"] == "partly_upheld"
        and detail["decision"]["actions_recommended"] == "A written warning."
    )
    assert detail["decision"]["decided_by"] == c.members["anti_ragging"][0]
    assert [x["id"] for x in detail["proceedings"]] == [p["id"]]
    closed = c.move(case["id"], "closed", "anti_ragging")  # no appeal on the ragging track: at once
    assert closed["status"] == "closed" and closed["closure"] == "decided" and closed["closed_at"]
    (event,) = outbox("grievance.case.closed", c.org.id)
    assert event["closure"] == "decided" and event["appealed"] is False and event["track"] == "ragging"
    actions = [a for a, _ in audit(c.org.id, case["id"])]
    assert actions == [
        "case.filed",
        "case.submitted_to_acknowledged",
        "case.acknowledged_to_under_inquiry",
        "proceeding.recorded",
        "case.decided",
        "case.decided_to_closed",
    ]


def test_not_admitting_needs_a_reason_and_the_complainant_sees_it(campus):
    c = campus
    case = c.file()
    path = f"/grievances/{case['id']}/status"
    r = c.post(path, {"status": "not_admitted"}, c.member())
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "reason_required")
    assert c.post(path, {"status": "not_admitted", "reason": "ab"}, c.member()).status_code == 422
    done = c.ok(c.post(path, {"status": "not_admitted", "reason": "Outside the committee's remit."}, c.member()))
    assert done["status"] == "not_admitted" and done["closure"] == "not_admitted" and done["closed_at"]
    mine = c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))
    assert mine["status"] == "not_admitted" and mine["not_admitted_reason"] == "Outside the committee's remit."
    (event,) = outbox("grievance.case.closed", c.org.id)
    assert event["closure"] == "not_admitted"
    assert ("case.submitted_to_not_admitted", "Outside the committee's remit.") in audit(c.org.id, case["id"])
    again = c.post(path, {"status": "acknowledged"}, c.member())
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "invalid_status")


def test_status_moves_outside_the_diagram_are_refused(campus):
    c = campus
    case = c.file()
    path = f"/grievances/{case['id']}/status"
    for target in ("under_inquiry", "closed"):
        r = c.post(path, {"status": target}, c.member())
        assert (r.status_code, r.json()["detail"]["code"]) == (409, "invalid_status"), target
    for target in ("decided", "withdrawn", "appealed", "submitted", "nonsense"):
        assert c.post(path, {"status": target}, c.member()).status_code == 422, target
    c.move(case["id"], "acknowledged")
    assert c.post(path, {"status": "not_admitted", "reason": "too late"}, c.member()).status_code == 409
    assert c.post(path, {"status": "acknowledged"}, c.member()).status_code == 409
    assert outbox("grievance.case.closed", c.org.id) == []


def test_proceedings_updates_and_decisions_need_the_right_status(campus):
    c = campus
    case = c.file()
    base = f"/grievances/{case['id']}"
    proceeding = {"kind": "note", "held_on": "2026-11-03", "summary": "A note."}
    decision = {"outcome": "upheld", "findings": "Found."}
    assert c.post(f"{base}/proceedings", proceeding, c.member()).status_code == 409  # still submitted
    assert c.post(f"{base}/decision", decision, c.member()).status_code == 409
    c.move(case["id"], "acknowledged")
    assert c.post(f"{base}/proceedings", proceeding, c.member()).status_code == 201
    r = c.post(f"{base}/decision", decision, c.member())  # acknowledged, not yet under inquiry
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "invalid_status")
    c.move(case["id"], "under_inquiry")
    assert c.post(f"{base}/decision", decision, c.member()).status_code == 200
    assert c.post(f"{base}/proceedings", proceeding, c.member()).status_code == 409  # decided
    assert c.post(f"{base}/decision", decision, c.member()).status_code == 409  # only once
    assert c.post(f"{base}/updates", {"body": "The decision stands."}, c.member()).status_code == 201


def test_messages_notify_the_other_side_with_the_case_number_only(campus):
    c = campus
    case = c.file()
    notifier.sent.clear()
    c.ok(c.post(f"/grievances/{case['id']}/updates", {"body": "Secret request for information."}, c.member()))
    assert [(n["person_id"], n["case_number"]) for n in notifier.sent] == [(c.complainant_id, case["number"])]
    notifier.sent.clear()
    c.ok(c.post(f"/me/grievances/{case['id']}/updates", {"body": "Secret answer."}, c.complainant))
    assert [(n["person_id"], n["case_number"]) for n in notifier.sent] == [(c.members["sgrc"][0], case["number"])]
    assert all("Secret" not in repr(n) for n in notifier.sent)
    notifier.sent.clear()
    c.move(case["id"], "acknowledged")
    c.ok(
        c.post(
            f"/grievances/{case['id']}/proceedings",
            {"kind": "note", "held_on": "2026-11-04", "summary": "Note."},
            c.member(),
        )
    )
    assert [n["person_id"] for n in notifier.sent] == [c.complainant_id]  # a proceeding notifies nobody
    assert ("update.added", None) in audit(c.org.id, case["id"])


def test_transfer_moves_the_case_and_its_track(campus):
    c = campus
    case = c.file()  # a student grievance that is really a ragging complaint
    target = c.committees["anti_ragging"]["id"]
    notifier.sent.clear()
    r = c.ok(
        c.post(f"/grievances/{case['id']}/transfer", {"committee_id": target, "reason": "It is ragging."}, c.member())
    )
    assert r["committee_id"] == target and r["track"] == "ragging" and r["status"] == "submitted"
    assert [n["person_id"] for n in notifier.sent] == [c.members["anti_ragging"][0]]
    assert ("case.transferred", "It is ragging.") in audit(c.org.id, case["id"])
    # the old committee no longer sees it; the new one does
    assert c.get(f"/grievances/{case['id']}", c.member("sgrc")).status_code == 404
    assert c.get(f"/grievances/{case['id']}", c.member("anti_ragging")).status_code == 200
    assert c.ok(c.get("/me/grievances", c.complainant))["items"][0]["track"] == "ragging"


def test_transfer_refusals(campus):
    c = campus
    case = c.file()
    path = f"/grievances/{case['id']}/transfer"
    inactive = c.ok(c.post("/committees", {"name": "Dormant", "kind": "icc", "active": False}))
    body = {"reason": "Wrong place"}
    assert (
        c.post(path, {**body, "committee_id": c.committees["sgrc"]["id"]}, c.member()).json()["detail"]["code"]
        == "same_committee"
    )
    assert (
        c.post(path, {**body, "committee_id": inactive["id"]}, c.member()).json()["detail"]["code"]
        == "committee_inactive"
    )
    r = c.post(path, {**body, "committee_id": c.committees["ombudsperson"]["id"]}, c.member())
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "committee_kind_invalid")
    assert c.post(path, {**body, "committee_id": new_id()}, c.member()).status_code == 404
    assert c.post(path, {"committee_id": c.committees["icc"]["id"]}, c.member()).status_code == 422
    assert c.post(path, {"committee_id": c.committees["icc"]["id"], "reason": "x"}, c.member()).status_code == 422
    c.decide(case["id"])
    r = c.post(path, {**body, "committee_id": c.committees["icc"]["id"]}, c.member())
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "invalid_status")


def test_a_final_case_takes_no_more_messages(campus):
    c = campus
    case = c.file()
    c.ok(c.post(f"/me/grievances/{case['id']}/withdraw", None, c.complainant))
    r = c.post(f"/grievances/{case['id']}/updates", {"body": "Too late."}, c.member())
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "case_final")


def test_input_bounds_on_the_committee_side(campus):
    c = campus
    case = c.file()
    c.to_inquiry(case["id"])
    base = f"/grievances/{case['id']}"
    for body in (
        {"kind": "hearing", "held_on": "1800-01-01", "summary": "abc"},
        {"kind": "hearing", "held_on": "2200-01-01", "summary": "abc"},
        {"kind": "hearing", "held_on": "2026-11-01", "summary": "ab"},
        {"kind": "hearing", "held_on": "2026-11-01", "summary": "a" * 20_001},
        {"kind": "trial", "held_on": "2026-11-01", "summary": "abc"},
        {"kind": "hearing", "held_on": "soon", "summary": "abc"},
    ):
        assert c.post(f"{base}/proceedings", body, c.member()).status_code == 422, body
    for body in (
        {"outcome": "maybe", "findings": "abc"},
        {"outcome": "upheld", "findings": "ab"},
        {"outcome": "upheld", "findings": "abc", "actions_recommended": "a" * 20_001},
        {"outcome": "upheld"},
    ):
        assert c.post(f"{base}/decision", body, c.member()).status_code == 422, body
    for body in ({"body": ""}, {"body": "   "}, {"body": "a" * 20_001}, {}):
        assert c.post(f"{base}/updates", body, c.member()).status_code == 422, body
        assert c.post(f"/me/grievances/{case['id']}/updates", body, c.complainant).status_code == 422, body
