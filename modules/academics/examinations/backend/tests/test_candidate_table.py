"""The candidate table (PRD 5.6), schema only: the unique key `(organisation_id, exam_paper_id, student_id)` that implements
"One per (exam paper, student)", and the NOT NULL columns. Nothing creates or reads candidates yet, so the rows here are
written straight through the model. The migration and its types are checked in test_migrations.py."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import BASE, make_cycle, make_grading, make_papers, ok, session_for, uid  # noqa: E402
from eos_examinations.infrastructure.models import CandidateRow  # noqa: E402
from sqlalchemy import text  # noqa: E402
from sqlalchemy.exc import IntegrityError  # noqa: E402


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


@pytest.fixture
def papers(client, h, cycle) -> list[dict]:
    """Two papers of one cycle (the INT and END components of one offering)."""
    return make_papers(client, h, cycle["id"])


def candidate(org_id: str, paper: dict, student_id: str, **over) -> CandidateRow:
    values = {
        "organisation_id": org_id,
        "exam_cycle_id": paper["exam_cycle_id"],
        "exam_paper_id": paper["id"],
        "course_offering_id": paper["course_offering_id"],
        "student_id": student_id,
        "eligibility_status": "pending",
        "eligibility_reasons": [],
        **over,
    }
    return CandidateRow(**values)


def add(org_id: str, *rows: CandidateRow) -> None:
    with session_for(org_id) as db:
        db.add_all(rows)
        db.commit()


def count(org_id: str, paper_id: str) -> int:
    with session_for(org_id) as db:
        return db.execute(
            text("SELECT count(*) FROM examinations_candidate WHERE organisation_id = :o AND exam_paper_id = :p"),
            {"o": org_id, "p": paper_id},
        ).scalar_one()


def test_a_second_candidate_for_the_same_organisation_paper_and_student_is_rejected(client, org, papers):
    paper, student = papers[0], uid()
    add(org.id, candidate(org.id, paper, student))
    with pytest.raises(IntegrityError):
        add(org.id, candidate(org.id, paper, student, eligibility_status="eligible"))
    assert count(org.id, paper["id"]) == 1


def test_the_same_paper_and_student_in_another_organisation_is_a_different_candidate(client, org, other_org, papers):
    """The organisation is part of the key. The paper row is shared here only because nothing checks that the paper
    belongs to the candidate's organisation (a later workstream creates candidates from the paper's own organisation)."""
    paper, student = papers[0], uid()
    add(org.id, candidate(org.id, paper, student))
    add(other_org.id, candidate(other_org.id, paper, student))
    assert count(org.id, paper["id"]) == 1 and count(other_org.id, paper["id"]) == 1


def test_the_same_student_may_be_a_candidate_for_a_different_paper(client, org, papers):
    student = uid()
    add(org.id, candidate(org.id, papers[0], student), candidate(org.id, papers[1], student))
    assert count(org.id, papers[0]["id"]) == 1 and count(org.id, papers[1]["id"]) == 1


def test_a_different_student_may_be_a_candidate_for_the_same_paper(client, org, papers):
    add(org.id, candidate(org.id, papers[0], uid()), candidate(org.id, papers[0], uid()))
    assert count(org.id, papers[0]["id"]) == 2


def test_a_null_organisation_is_rejected_so_the_key_cannot_be_bypassed(client, org, papers):
    """With a NULL member a unique key lets duplicates through on Postgres and SQLite; the column is NOT NULL instead."""
    paper, student = papers[0], uid()
    insert = text(
        "INSERT INTO examinations_candidate (id, organisation_id, created_at, exam_cycle_id, exam_paper_id, "
        "course_offering_id, student_id, eligibility_status, eligibility_reasons) "
        "VALUES (:id, NULL, '2026-11-13 00:00:00', :cycle, :paper, :offering, :student, 'pending', '[]')"
    )
    params = {
        "cycle": paper["exam_cycle_id"],
        "paper": paper["id"],
        "offering": paper["course_offering_id"],
        "student": student,
    }
    for _ in range(2):  # not even a first row, let alone two with the same paper and student
        with session_for(org.id) as db:
            with pytest.raises(IntegrityError):
                db.execute(insert, {"id": uid(), **params})
                db.commit()
    with session_for(org.id) as db:
        with pytest.raises(IntegrityError):
            db.add(candidate(None, paper, student))
            db.commit()


@pytest.mark.parametrize("column", ["eligibility_status", "eligibility_reasons"])
def test_the_eligibility_columns_have_no_default_and_reject_none(client, org, papers, column):
    """The writer sets them. A Python None is stored as SQL NULL (`JSON(none_as_null=True)`), not as a JSON null that
    would pass NOT NULL."""
    with session_for(org.id) as db:
        with pytest.raises(IntegrityError):
            db.add(candidate(org.id, papers[0], uid(), **{column: None}))
            db.commit()


def test_the_override_and_determination_columns_are_optional_and_the_reasons_round_trip(client, org, papers):
    row_id, actor = uid(), uid()
    reasons = [{"code": "attendance_shortage", "detail": "62%"}]
    add(org.id, candidate(org.id, papers[0], uid()))  # none of the optional columns given
    add(
        org.id,
        candidate(
            org.id,
            papers[1],
            uid(),
            id=row_id,
            eligibility_reasons=reasons,
            overridden_by=actor,
            override_reason="x" * 500,
        ),
    )
    with session_for(org.id) as db:
        plain = db.query(CandidateRow).filter_by(exam_paper_id=papers[0]["id"]).one()
        assert (plain.overridden_by, plain.override_reason, plain.determined_at) == (None, None, None)
        assert plain.eligibility_reasons == []
        full = db.get(CandidateRow, row_id)
        assert full.eligibility_reasons == reasons and full.overridden_by == actor and len(full.override_reason) == 500
