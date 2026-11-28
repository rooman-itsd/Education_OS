"""Decision D5 (issue #325): a person who evaluates a paper does not moderate the same paper, in either order. Duty
assignment refuses the pairing; the marks operations refuse a person who holds both anyway (a pairing that exists
already). Other papers, other people and other duty types are untouched."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    err,
    make_cycle,
    make_duty,
    make_grading,
    make_papers,
    ok,
    session_for,
    set_row,
    uid,
)
from eos_examinations.infrastructure.models import CandidateRow, ExamDutyRow, ExamPaperRow  # noqa: E402

PAPERS = f"{BASE}/papers"


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


@pytest.fixture
def papers(client, h, cycle) -> list[dict]:
    return make_papers(client, h, cycle["id"], None, ["END"]) + make_papers(client, h, cycle["id"], None, ["END"])


def assign(client, h, staff_id, duty_type, paper_id):
    return client.post(
        f"{BASE}/duties", json={"staff_id": staff_id, "duty_type": duty_type, "exam_paper_id": paper_id}, headers=h
    )


def test_an_evaluator_is_not_assigned_to_moderate_the_same_paper(client, org, h, papers):
    first, second = papers
    staff, _ = org.user(FACULTY)
    evaluation = make_duty(client, h, staff, "evaluation", paper_id=first["id"])
    detail = err(assign(client, h, staff, "moderation", first["id"]), 409, "duty_separation")
    assert (
        detail["details"]["conflicting_duty_type"] == "evaluation"
        and detail["details"]["exam_duty_id"] == evaluation["id"]
    )
    # Another paper is a different matter, and so is another person.
    ok(assign(client, h, staff, "moderation", second["id"]), 201)
    other, _ = org.user(FACULTY)
    ok(assign(client, h, other, "moderation", first["id"]), 201)


def test_a_moderator_is_not_assigned_to_evaluate_the_same_paper(client, org, h, papers):
    first, second = papers
    staff, _ = org.user(FACULTY)
    make_duty(client, h, staff, "moderation", paper_id=first["id"])
    detail = err(assign(client, h, staff, "evaluation", first["id"]), 409, "duty_separation")
    assert detail["details"]["conflicting_duty_type"] == "moderation"
    ok(assign(client, h, staff, "evaluation", second["id"]), 201)


def test_a_cancelled_duty_no_longer_separates(client, org, h, papers):
    first, _ = papers
    staff, _ = org.user(FACULTY)
    evaluation = make_duty(client, h, staff, "evaluation", paper_id=first["id"])
    err(assign(client, h, staff, "moderation", first["id"]), 409, "duty_separation")
    ok(client.post(f"{BASE}/duties/{evaluation['id']}/cancel", json={"reason": "reassigned"}, headers=h))
    ok(assign(client, h, staff, "moderation", first["id"]), 201)


def hold(org, paper, staff, duty_type):
    """A duty written straight through the model: the pairing the assignment now refuses, as data that predates it."""
    with session_for(org.id) as db:
        db.add(
            ExamDutyRow(
                organisation_id=org.id,
                exam_cycle_id=paper["exam_cycle_id"],
                staff_id=staff,
                duty_type=duty_type,
                exam_paper_id=paper["id"],
                status="assigned",
            )
        )
        db.commit()


def candidate(org, paper) -> str:
    row = CandidateRow(
        organisation_id=org.id,
        exam_cycle_id=paper["exam_cycle_id"],
        exam_paper_id=paper["id"],
        course_offering_id=paper["course_offering_id"],
        student_id=uid(),
        eligibility_status="eligible",
        eligibility_reasons=[],
    )
    with session_for(org.id) as db:
        db.add(row)
        db.commit()
        return row.id


def test_marks_operations_refuse_a_person_who_holds_both_duties_on_the_paper(client, org, h, papers):
    paper = papers[0]
    staff, headers = org.user(FACULTY)
    cand = candidate(org, paper)
    hold(org, paper, staff, "evaluation")
    hold(org, paper, staff, "moderation")
    entry = {"candidate_id": cand, "marks_obtained": 10}

    set_row(org.id, ExamPaperRow, paper["id"], status="marks_entry")
    err(client.put(f"{PAPERS}/{paper['id']}/marks", json={"entries": [entry]}, headers=headers), 409, "duty_separation")
    err(client.post(f"{PAPERS}/{paper['id']}/marks/submit", headers=headers), 409, "duty_separation")

    set_row(org.id, ExamPaperRow, paper["id"], status="moderation")
    detail = err(
        client.post(
            f"{PAPERS}/{paper['id']}/moderation", json={"reason": "scaling", "uniform_delta": 1}, headers=headers
        ),
        409,
        "duty_separation",
    )
    assert detail["details"]["conflicting_duty_type"] == "evaluation"


def test_a_controller_with_no_duty_still_enters_marks_and_a_single_duty_still_works(client, org, h, papers):
    paper = papers[0]
    cand = candidate(org, paper)
    set_row(org.id, ExamPaperRow, paper["id"], status="marks_entry")
    entry = {"candidate_id": cand, "marks_obtained": 10}
    assert client.put(f"{PAPERS}/{paper['id']}/marks", json={"entries": [entry]}, headers=h).status_code == 200
    staff, headers = org.user(FACULTY)
    make_duty(client, h, staff, "evaluation", paper_id=paper["id"])
    assert client.put(f"{PAPERS}/{paper['id']}/marks", json={"entries": [entry]}, headers=headers).status_code == 200
