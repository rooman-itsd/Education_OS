"""Filing a complaint and reading one's own cases (docs/prd.md "Main flows" 2, 5, 9)."""

from conftest import DESCRIPTION, audit, outbox
from eos_core.db import new_id
from eos_grievance.infrastructure import notifier


def test_filing_creates_a_numbered_submitted_case_and_tells_the_committee(campus):
    c = campus
    case = c.file(
        category="Fees",
        incident_date="2026-10-30",
        respondent={"person_id": new_id(), "description": "Accounts clerk"},
    )
    assert case["number"] == "GRV-000001" and case["status"] == "submitted"
    assert case["track"] == "student_grievance" and case["committee_id"] == c.committees["sgrc"]["id"]
    assert case["can_appeal"] is False and case["incident_date"] == "2026-10-30"
    assert "respondent" not in case and "complainant_id" not in case
    second = c.file()
    assert second["number"] == "GRV-000002"
    assert notifier.sent[0]["person_id"] == c.members["sgrc"][0]
    assert notifier.sent[0]["message"] == f"There is an update on case {case['number']}."
    assert set(notifier.sent[0]) == {"organisation_id", "person_id", "case_number", "message"}
    assert audit(c.org.id, case["id"]) == [("case.filed", None)]


def test_filing_publishes_the_filed_event_with_metadata_only(campus):
    c = campus
    case = c.file(description="A long private description of the complaint that must stay private.")
    (payload,) = outbox("grievance.case.filed", c.org.id)
    assert payload == {
        "organisation_id": c.org.id,
        "case_id": case["id"],
        "number": case["number"],
        "track": "student_grievance",
        "committee_id": c.committees["sgrc"]["id"],
        "filed_at": case["filed_at"],
    }


def test_case_numbers_are_per_organisation_and_use_the_prefix(campus, other_org, monkeypatch):
    c = campus
    monkeypatch.setenv("GRIEVANCE_CASE_NUMBER_PREFIX", "SGR")
    assert c.file()["number"] == "SGR-000001"
    other = type(c)(c.client, other_org)
    assert other.file()["number"] == "SGR-000001"
    assert c.file()["number"] == "SGR-000002"


def test_each_track_goes_to_the_committee_of_its_kind(campus):
    c = campus
    ragging = c.file("ragging")
    assert ragging["committee_id"] == c.committees["anti_ragging"]["id"]
    harassment = c.file("sexual_harassment")
    assert harassment["committee_id"] == c.committees["icc"]["id"]


def test_the_committee_is_required_when_there_are_several_and_must_fit(campus):
    c = campus
    second = c.ok(c.post("/committees", {"name": "SGRC North", "kind": "sgrc"}))
    r = c.post(
        "/me/grievances", {"track": "student_grievance", "category": "x", "description": DESCRIPTION}, c.complainant
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "committee_required")
    assert c.file(committee_id=second["id"])["committee_id"] == second["id"]
    wrong = c.post(
        "/me/grievances",
        {"track": "ragging", "committee_id": second["id"], "category": "x", "description": DESCRIPTION},
        c.complainant,
    )
    assert (wrong.status_code, wrong.json()["detail"]["code"]) == (422, "committee_wrong_kind")
    ghost = {"track": "ragging", "committee_id": new_id(), "category": "x", "description": DESCRIPTION}
    assert c.post("/me/grievances", ghost, c.complainant).json()["detail"]["code"] == "committee_not_found"
    third = c.ok(c.post("/committees", {"name": "SGRC South", "kind": "sgrc", "active": False}))
    inactive = {"track": "student_grievance", "committee_id": third["id"], "category": "x", "description": DESCRIPTION}
    assert c.post("/me/grievances", inactive, c.complainant).json()["detail"]["code"] == "committee_inactive"
    c.ok(c.patch(f"/committees/{c.committees['icc']['id']}", {"active": False}))
    r = c.post(
        "/me/grievances", {"track": "sexual_harassment", "category": "x", "description": DESCRIPTION}, c.complainant
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "no_active_committee")


def test_my_cases_newest_first_filtered_and_paged(campus, clock):
    c = campus
    ids = []
    for _ in range(3):
        ids.append(c.file()["id"])
        clock.advance(minutes=5)
    c.file(headers=c.other)  # someone else's
    page = c.ok(c.get("/me/grievances?limit=2", c.complainant))
    assert [x["id"] for x in page["items"]] == [ids[2], ids[1]] and page["next_cursor"]
    rest = c.ok(c.get(f"/me/grievances?limit=2&cursor={page['next_cursor']}", c.complainant))
    assert [x["id"] for x in rest["items"]] == [ids[0]] and rest["next_cursor"] is None
    c.ok(c.post(f"/me/grievances/{ids[0]}/withdraw", None, c.complainant))
    only = c.ok(c.get("/me/grievances?status=withdrawn,closed", c.complainant))
    assert [x["id"] for x in only["items"]] == [ids[0]]
    assert len(c.ok(c.get("/me/grievances?status=submitted", c.complainant))["items"]) == 2


def test_my_case_shows_updates_and_never_proceedings(campus):
    c = campus
    case = c.file()
    c.move(case["id"], "acknowledged")
    proceeding = {"kind": "hearing", "held_on": "2026-11-04", "summary": "Committee-only hearing notes."}
    c.ok(c.post(f"/grievances/{case['id']}/proceedings", proceeding, c.member()))
    c.ok(c.post(f"/grievances/{case['id']}/updates", {"body": "Please send the receipt."}, c.member()))
    c.ok(c.post(f"/me/grievances/{case['id']}/updates", {"body": "Receipt attached."}, c.complainant))
    mine = c.ok(c.get(f"/me/grievances/{case['id']}", c.complainant))
    assert "proceedings" not in mine and "respondent" not in mine
    assert [(u["from_committee"], u["body"]) for u in mine["updates"]] == [
        (True, "Please send the receipt."),
        (False, "Receipt attached."),
    ]
    assert mine["decision"] is None and mine["appeal"] is None and mine["not_admitted_reason"] is None
    assert "Committee-only hearing notes." not in c.get(f"/me/grievances/{case['id']}", c.complainant).text


def test_another_persons_case_is_not_found(campus):
    c = campus
    case = c.file()
    path = f"/me/grievances/{case['id']}"
    assert c.get(path, c.other).status_code == 404
    assert c.post(f"{path}/updates", {"body": "hello"}, c.other).status_code == 404
    assert c.post(f"{path}/withdraw", None, c.other).status_code == 404
    assert c.post(f"{path}/appeal", {"reason": "I disagree with this."}, c.other).status_code == 404
    assert c.get(f"/me/grievances/{new_id()}", c.complainant).status_code == 404
    assert c.get("/me/grievances/not-a-uuid", c.complainant).status_code == 404


def test_withdrawing_before_a_decision_closes_the_case(campus):
    c = campus
    case = c.file()
    r = c.ok(c.post(f"/me/grievances/{case['id']}/withdraw", {"reason": "Resolved with the warden"}, c.complainant))
    assert r["status"] == "withdrawn" and r["closed_at"]
    (payload,) = outbox("grievance.case.closed", c.org.id)
    assert payload == {
        "organisation_id": c.org.id,
        "case_id": case["id"],
        "number": case["number"],
        "track": "student_grievance",
        "committee_id": c.committees["sgrc"]["id"],
        "closure": "withdrawn",
        "appealed": False,
        "closed_at": r["closed_at"],
    }
    assert ("case.withdrawn", "Resolved with the warden") in audit(c.org.id, case["id"])
    again = c.post(f"/me/grievances/{case['id']}/withdraw", None, c.complainant)
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "invalid_status")
    update = c.post(f"/me/grievances/{case['id']}/updates", {"body": "hello"}, c.complainant)
    assert (update.status_code, update.json()["detail"]["code"]) == (409, "case_final")
    assert len(outbox("grievance.case.closed", c.org.id)) == 1


def test_a_decided_case_cannot_be_withdrawn(campus):
    c = campus
    case = c.file()
    c.decide(case["id"])
    r = c.post(f"/me/grievances/{case['id']}/withdraw", None, c.complainant)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "invalid_status")
    assert outbox("grievance.case.closed", c.org.id) == []


def test_filing_input_is_validated(campus):
    c = campus
    ok = {"track": "student_grievance", "category": "x", "description": DESCRIPTION}
    bad = [
        {**ok, "track": "bullying"},
        {**ok, "description": "too short"},
        {**ok, "description": "x" * 20_001},
        {**ok, "category": ""},
        {**ok, "category": "c" * 81},
        {**ok, "incident_date": "1800-01-01"},
        {**ok, "incident_date": "9999-12-31"},
        {**ok, "incident_date": "not a date"},
        {**ok, "committee_id": "mine"},
        {**ok, "respondent": {"person_id": "x"}},
        {**ok, "respondent": {"description": "d" * 501}},
        {**ok, "respondent": {"unknown": 1}},
        {**ok, "complainant_id": new_id()},
        {"track": "student_grievance", "category": "x"},
    ]
    for body in bad:
        assert c.post("/me/grievances", body, c.complainant).status_code == 422, body
    assert (
        c.post("/me/grievances", {**ok, "respondent": {}, "incident_date": "2199-12-31"}, c.complainant).status_code
        == 201
    )
    assert c.post("/me/grievances", {**ok, "respondent": None}, c.complainant).status_code == 201
