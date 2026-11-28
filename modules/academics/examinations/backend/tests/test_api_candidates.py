"""determineEligibility, listCandidates and overrideCandidateEligibility (FR-7; decisions D2 and D7, issue #325).
Registrations reach the module the way they do in production, through the consumers (`deliver`), with the payloads
enrolment-registration publishes; no registration row is inserted by hand."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    HEAD,
    STUDENT,
    all_outbox,
    audit_entries,
    err,
    make_cycle,
    make_grading,
    make_papers,
    ok,
    session_for,
    set_row,
    uid,
)
from eos_examinations.application.consumers import REGISTRATION_CONFIRMED, REGISTRATION_WITHDRAWN  # noqa: E402
from eos_examinations.infrastructure.models import CandidateRow, ExamCycleRow, MarkEntryRow  # noqa: E402
from test_consumers import deliver  # noqa: E402
from test_consumers_registration import confirmed, withdrawn  # noqa: E402

CANDIDATES = f"{BASE}/candidates"
EVENT = "examinations.candidate.eligibility-determined"


@pytest.fixture(autouse=True)
def _registration_tables():
    from eos_core.db import init_db

    init_db()


@pytest.fixture
def scheme(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return scheme


def cycle_of(client, h, scheme, **over) -> dict:
    return make_cycle(client, h, scheme["id"], **over)


def register(org, cycle, paper, kind="regular") -> dict:
    """A confirmed registration of a new student in the paper's offering, in the cycle's academic period."""
    payload = confirmed(
        registration_type=kind,
        course_offering_id=paper["course_offering_id"],
        academic_period_id=cycle["academic_period_id"],
    )
    deliver(org.id, REGISTRATION_CONFIRMED, payload)
    return payload


def run(client, h, cycle, **body):
    return client.post(f"{BASE}/exam-cycles/{cycle['id']}/eligibility-runs", json=body or None, headers=h)


def candidates(client, h, query: str = "") -> dict:
    return ok(client.get(f"{CANDIDATES}{query}", headers=h))


def events(org) -> int:
    return all_outbox(org.id).count(EVENT)


def test_a_run_makes_a_candidate_of_each_registered_student_and_leaves_them_pending(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    a, b = register(org, cycle, paper), register(org, cycle, paper)
    summary = ok(run(client, h, cycle))
    assert summary == {"exam_cycle_id": cycle["id"], "candidates": 2, "eligible": 0, "ineligible": 0, "pending": 2}
    listing = candidates(client, h, f"?exam_cycle_id={cycle['id']}")
    assert listing["total"] == 2
    assert {c["student_id"] for c in listing["items"]} == {a["person_id"], b["person_id"]}
    for item in listing["items"]:
        assert (item["exam_paper_id"], item["course_offering_id"]) == (paper["id"], paper["course_offering_id"])
        # student status has no source yet: the candidate is pending, with no reason, and the input is named
        assert (item["eligibility_status"], item["eligibility_reasons"]) == ("pending", [])
        assert item["pending_inputs"] == ["student_status"] and item["overridden_by"] is None and item["determined_at"]
    assert events(org) == 2  # one event per student


def test_the_cycles_own_minimum_attendance_and_dues_setting_decide_which_inputs_are_missing(client, org, h, scheme):
    plain = cycle_of(client, h, scheme, code="PLAIN")
    strict = cycle_of(client, h, scheme, code="STRICT", min_attendance_percent=75, check_dues=True)
    lenient = cycle_of(client, h, scheme, code="LENIENT", min_attendance_percent=60)
    for cycle in (plain, strict, lenient):
        paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
        register(org, cycle, paper)
        ok(run(client, h, cycle))
    pending = {c["exam_cycle_id"]: c["pending_inputs"] for c in candidates(client, h)["items"]}
    assert pending[plain["id"]] == ["student_status"]
    assert pending[strict["id"]] == ["student_status", "attendance", "dues"]
    assert pending[lenient["id"]] == ["student_status", "attendance"]


def test_a_second_run_changes_nothing_and_publishes_nothing(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    register(org, cycle, paper)
    ok(run(client, h, cycle))
    first = candidates(client, h)["items"]
    sent, audited = events(org), len(audit_entries(org.id))
    assert ok(run(client, h, cycle))["candidates"] == 1
    assert candidates(client, h)["items"] == first  # determined_at included: nothing was rewritten
    assert (events(org), len(audit_entries(org.id))) == (sent, audited)


@pytest.mark.parametrize(
    ("cycle_type", "kinds", "expected"),
    [
        ("end_term", ("regular", "supplementary", "backlog"), ["regular"]),
        ("supplementary", ("regular", "supplementary", "backlog"), ["supplementary", "backlog"]),
    ],
)
def test_each_registration_type_makes_a_candidate_only_in_the_cycles_the_rule_names(
    client, org, h, scheme, cycle_type, kinds, expected
):
    cycle = cycle_of(client, h, scheme, cycle_type=cycle_type)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    by_student = {register(org, cycle, paper, kind)["person_id"]: kind for kind in kinds}
    ok(run(client, h, cycle))
    made = {c["student_id"] for c in candidates(client, h)["items"]}
    assert sorted(by_student[s] for s in made) == sorted(expected)


def test_registrations_of_another_period_or_offering_make_no_candidate(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    other_period = confirmed(course_offering_id=paper["course_offering_id"], academic_period_id=uid())
    other_offering = confirmed(academic_period_id=cycle["academic_period_id"])
    deliver(org.id, REGISTRATION_CONFIRMED, other_period)
    deliver(org.id, REGISTRATION_CONFIRMED, other_offering)
    mine = register(org, cycle, paper)
    assert ok(run(client, h, cycle))["candidates"] == 1
    assert [c["student_id"] for c in candidates(client, h)["items"]] == [mine["person_id"]]


def test_a_withdrawn_registration_makes_no_candidate_and_turns_an_existing_one_ineligible(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    kept, dropped, never = register(org, cycle, paper), register(org, cycle, paper), register(org, cycle, paper)
    deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(never))  # withdrawn before any run
    summary = ok(run(client, h, cycle))
    assert (summary["candidates"], summary["pending"]) == (2, 2)  # the one withdrawn before the run is no candidate
    deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(dropped))
    sent = events(org)
    summary = ok(run(client, h, cycle))
    assert (summary["candidates"], summary["pending"], summary["ineligible"]) == (2, 1, 1)
    by_student = {c["student_id"]: c for c in candidates(client, h)["items"]}
    assert by_student[dropped["person_id"]]["eligibility_status"] == "ineligible"
    assert [r["code"] for r in by_student[dropped["person_id"]]["eligibility_reasons"]] == ["not_registered"]
    assert by_student[kept["person_id"]]["eligibility_status"] == "pending"
    assert never["person_id"] not in by_student
    assert events(org) == sent + 1  # only the student whose candidacy changed


def test_a_run_can_be_limited_to_some_papers(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    first, second = (make_papers(client, h, cycle["id"], None, ["END"])[0] for _ in range(2))
    register(org, cycle, first)
    register(org, cycle, second)
    ok(run(client, h, cycle, exam_paper_ids=[first["id"]]))
    assert [c["exam_paper_id"] for c in candidates(client, h)["items"]] == [first["id"]]
    err(run(client, h, cycle, exam_paper_ids=[uid()]), 404, "exam_paper_not_found")
    err(run(client, h, cycle, exam_paper_ids="all"), 400, "invalid_body")
    err(run(client, h, cycle, exam_paper_ids=["nope"]), 400, "invalid_id")
    ok(run(client, h, cycle))
    assert candidates(client, h)["total"] == 2


def test_a_run_is_refused_for_an_unknown_cycle_other_roles_and_a_cycle_with_published_results(
    client, org, other_org, h, scheme
):
    cycle = cycle_of(client, h, scheme)
    err(client.post(f"{BASE}/exam-cycles/{uid()}/eligibility-runs", headers=h), 404, "exam_cycle_not_found")
    assert (
        client.post(f"{BASE}/exam-cycles/{cycle['id']}/eligibility-runs", headers=other_org.controller()).status_code
        == 404
    )
    for role in (FACULTY, STUDENT, HEAD):
        _, headers = org.user(role)
        assert client.post(f"{BASE}/exam-cycles/{cycle['id']}/eligibility-runs", headers=headers).status_code == 403, (
            role
        )
    assert client.post(f"{BASE}/exam-cycles/{cycle['id']}/eligibility-runs").status_code == 401
    set_row(org.id, ExamCycleRow, cycle["id"], status="results_published")
    err(run(client, h, cycle), 409, "cycle_results_published")


def first_candidate(client, h, cycle) -> dict:
    ok(run(client, h, cycle))
    return candidates(client, h, f"?exam_cycle_id={cycle['id']}")["items"][0]


def test_an_override_sets_the_status_with_its_reason_is_audited_and_survives_later_runs(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    register(org, cycle, paper)
    cand = first_candidate(client, h, cycle)
    sent = events(org)
    body = ok(
        client.patch(
            f"{CANDIDATES}/{cand['id']}",
            json={"eligibility_status": "eligible", "reason": "attendance condoned"},
            headers=h,
        )
    )
    assert body["eligibility_status"] == "eligible" and body["pending_inputs"] == []
    assert body["eligibility_reasons"] == [{"code": "manual_override", "detail": "attendance condoned"}]
    assert body["overridden_by"]
    assert events(org) == sent + 1
    (entry,) = [a for a in audit_entries(org.id, cand["id"]) if a.action == "candidate.overridden"]
    assert entry.after["eligibility_status"] == "eligible"
    ok(run(client, h, cycle))  # a later run keeps the override
    assert candidates(client, h, f"?exam_paper_id={paper['id']}")["items"][0]["eligibility_status"] == "eligible"
    # and it can be overridden again, the other way
    again = ok(
        client.patch(
            f"{CANDIDATES}/{cand['id']}", json={"eligibility_status": "ineligible", "reason": "dues unpaid"}, headers=h
        )
    )
    assert again["eligibility_status"] == "ineligible"


def test_an_override_needs_a_status_a_reason_and_a_candidate_without_marks(client, org, other_org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    register(org, cycle, paper)
    cand = first_candidate(client, h, cycle)
    url = f"{CANDIDATES}/{cand['id']}"
    err(client.patch(url, json={"eligibility_status": "pending", "reason": "x"}, headers=h), 400, "invalid_choice")
    err(client.patch(url, json={"eligibility_status": "maybe", "reason": "x"}, headers=h), 400, "invalid_choice")
    err(client.patch(url, json={"eligibility_status": "eligible", "reason": "  "}, headers=h), 400, "invalid_text")
    err(client.patch(url, json={"eligibility_status": "eligible"}, headers=h), 400, "missing_field")
    err(
        client.patch(url, json={"eligibility_status": "eligible", "reason": "x" * 501}, headers=h), 400, "text_too_long"
    )
    err(
        client.patch(f"{CANDIDATES}/{uid()}", json={"eligibility_status": "eligible", "reason": "x"}, headers=h),
        404,
        "candidate_not_found",
    )
    body = {"eligibility_status": "eligible", "reason": "x"}
    assert client.patch(url, json=body, headers=other_org.controller()).status_code == 404
    for role in (FACULTY, STUDENT, HEAD):
        _, headers = org.user(role)
        assert client.patch(url, json=body, headers=headers).status_code == 403, role
    ok(client.patch(url, json=body, headers=h))
    with session_for(org.id) as db:
        db.add(
            MarkEntryRow(
                organisation_id=org.id,
                candidate_id=cand["id"],
                marks_obtained=10,
                absent=False,
                entered_by=uid(),
                entered_at=cand_time(),
                status="entered",
            )
        )
        db.commit()
    err(
        client.patch(url, json={"eligibility_status": "ineligible", "reason": "late"}, headers=h),
        409,
        "candidate_has_marks",
    )
    ok(client.patch(url, json={"eligibility_status": "eligible", "reason": "still fine"}, headers=h))
    set_row(org.id, ExamCycleRow, cycle["id"], status="closed")
    err(client.patch(url, json=body, headers=h), 409, "cycle_results_published")


def cand_time():
    from datetime import UTC, datetime

    return datetime(2026, 11, 5, 9, 0, tzinfo=UTC)


def test_a_run_leaves_a_candidate_with_marks_alone(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    gone = register(org, cycle, paper)
    cand = first_candidate(client, h, cycle)
    with session_for(org.id) as db:
        db.add(
            MarkEntryRow(
                organisation_id=org.id,
                candidate_id=cand["id"],
                marks_obtained=10,
                absent=False,
                entered_by=uid(),
                entered_at=cand_time(),
                status="entered",
            )
        )
        db.commit()
    deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(gone))
    ok(run(client, h, cycle))
    assert candidates(client, h)["items"][0]["eligibility_status"] == "pending"  # the marks stay with their candidate


def test_the_listing_filters_pages_and_is_for_the_organisation_wide_key_only(client, org, other_org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    papers = [make_papers(client, h, cycle["id"], None, ["END"])[0] for _ in range(2)]
    registered = [register(org, cycle, p) for p in papers for _ in range(2)]
    ok(run(client, h, cycle))
    one = candidates(client, h, f"?exam_paper_id={papers[0]['id']}")
    assert one["total"] == 2 and {c["exam_paper_id"] for c in one["items"]} == {papers[0]["id"]}
    assert candidates(client, h, f"?student_id={registered[0]['person_id']}")["total"] == 1
    assert candidates(client, h, f"?course_offering_id={papers[1]['course_offering_id']}")["total"] == 2
    assert candidates(client, h, "?eligibility_status=eligible")["total"] == 0
    assert candidates(client, h, "?eligibility_status=pending")["total"] == 4
    assert candidates(client, h, "?reason_code=not_registered")["total"] == 0
    page = candidates(client, h, "?limit=3&offset=2")
    assert (page["total"], len(page["items"])) == (4, 2)
    err(client.get(f"{CANDIDATES}?eligibility_status=nope", headers=h), 400, "invalid_choice")
    err(client.get(f"{CANDIDATES}?reason_code=nope", headers=h), 400, "invalid_choice")
    err(client.get(f"{CANDIDATES}?student_id=nope", headers=h), 400, "invalid_id")
    assert candidates(client, other_org.controller())["total"] == 0  # another organisation sees none of it
    # `candidate:read-department` alone grants nothing (the department is unknown, Q13); a student or faculty has no key
    for role in (HEAD, FACULTY, STUDENT):
        _, headers = org.user(role)
        assert client.get(CANDIDATES, headers=headers).status_code == 403, role
    assert client.get(CANDIDATES).status_code == 401


def test_the_reason_filter_finds_the_candidates_a_reason_was_recorded_for(client, org, h, scheme):
    cycle = cycle_of(client, h, scheme)
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    dropped, _ = register(org, cycle, paper), register(org, cycle, paper)
    ok(run(client, h, cycle))
    deliver(org.id, REGISTRATION_WITHDRAWN, withdrawn(dropped))
    ok(run(client, h, cycle))
    found = candidates(client, h, "?reason_code=not_registered")
    assert found["total"] == 1 and found["items"][0]["student_id"] == dropped["person_id"]
    with session_for(org.id) as db:
        assert db.query(CandidateRow).count() >= 2
