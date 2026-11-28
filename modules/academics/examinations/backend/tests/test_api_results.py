"""The results workflow (decision D4, FR-13 to FR-17): computeResults, approveResultsDepartment, approveResults,
publishResults, listResults, listMyResults and reviseResult. Candidates and marks are written through the model, because
nothing in the tests needs the whole marks pipeline to prepare them; the papers are locked with `set_row`. The clock is
frozen at 2026-11-05 (conftest.py)."""

from decimal import Decimal

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    CONTROLLER,
    FACULTY,
    HEAD,
    NOW,
    STUDENT,
    audit_entries,
    err,
    make_cycle,
    make_grading,
    make_papers,
    ok,
    outbox,
    session_for,
    set_row,
    uid,
)
from eos_examinations.infrastructure import repository as repo  # noqa: E402
from eos_examinations.infrastructure.models import (  # noqa: E402
    CandidateRow,
    ExamCycleRow,
    ExamPaperRow,
    MarkEntryRow,
    OfferingRef,
    ResultRow,
)
from test_api_contract import SCHEMAS, check, operation  # noqa: E402

D = Decimal


@pytest.fixture
def cycle(client, org, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    made = make_cycle(client, h)
    set_row(org.id, ExamCycleRow, made["id"], status="evaluation")
    return made


def offering(client, org, h, cycle, students, *, lock=True, codes=("INT", "END")) -> dict:
    """An offering with INT (40, max 100) and END (60, max 100) papers in the cycle, locked, and `students`: a list of
    (student_id, INT marks, END marks) each a candidate of both papers with locked marks. A marks value of None is
    `absent`."""
    set_row(org.id, ExamCycleRow, cycle["id"], status="draft")  # papers are made while a cycle is configurable
    papers = make_papers(client, h, cycle["id"], None, codes)
    by_code = {}
    for paper in papers:
        paper_row = ok(client.get(f"{BASE}/papers/{paper['id']}", headers=h))
        by_code[paper_row["component_code"]] = paper_row
        if lock:
            set_row(org.id, ExamPaperRow, paper["id"], status="locked")
    with session_for(org.id) as db:
        for student_id, *marks in students:
            for code, value in zip(codes, marks, strict=True):
                paper = by_code[code]
                candidate = CandidateRow(
                    organisation_id=org.id,
                    exam_cycle_id=cycle["id"],
                    exam_paper_id=paper["id"],
                    course_offering_id=paper["course_offering_id"],
                    student_id=student_id,
                    eligibility_status="eligible",
                    eligibility_reasons=[],
                )
                db.add(candidate)
                db.flush()
                db.add(
                    MarkEntryRow(
                        organisation_id=org.id,
                        candidate_id=candidate.id,
                        marks_obtained=None if value is None else D(str(value)),
                        absent=value is None,
                        entered_by=uid(),
                        entered_at=NOW,
                        status="locked",
                    )
                )
        db.commit()
    set_row(org.id, ExamCycleRow, cycle["id"], status="evaluation")
    return {"id": papers[0]["course_offering_id"], "papers": by_code}


def add_ref(org, offering_id: str, credits: float | None, code="CS101") -> None:
    with session_for(org.id) as db:
        db.add(
            OfferingRef(
                organisation_id=org.id,
                course_offering_id=offering_id,
                academic_period_id=uid(),
                course_code=code,
                course_title=f"{code} title",
                credits=None if credits is None else D(str(credits)),
            )
        )
        db.commit()


def url(cycle: dict, action: str) -> str:
    return f"{BASE}/exam-cycles/{cycle['id']}/results/{action}"


def compute(client, h, cycle, *offerings, status=200):
    body = {"course_offering_ids": list(offerings)} if offerings else None
    return ok(client.post(url(cycle, "compute"), json=body, headers=h), status)


def results(client, h, cycle, **query) -> list[dict]:
    query = {"exam_cycle_id": cycle["id"], "limit": 200, **query}
    return ok(client.get(f"{BASE}/results", params=query, headers=h))["items"]


def by_student(rows: list[dict]) -> dict[str, dict]:
    return {r["student_id"]: r for r in rows}


def through_approval(client, h, cycle, *offerings) -> None:
    body = {"course_offering_ids": list(offerings)} if offerings else None
    ok(client.post(url(cycle, "approve-department"), json=body, headers=h))
    ok(client.post(url(cycle, "approve"), json=body, headers=h))


# ---------------------------------------------------------------- compute


def test_computing_gives_each_student_a_percentage_grade_and_pass_from_the_scheme(client, org, h, cycle):
    s1, s2, s3 = uid(), uid(), uid()
    o = offering(client, org, h, cycle, [(s1, 80, 70), (s2, 10, None), (s3, 30, 30)])
    summary = compute(client, h, cycle)
    assert summary == {"exam_cycle_id": cycle["id"], "course_offerings": 1, "results": 3}
    rows = by_student(results(client, h, cycle))
    first = rows[s1]
    assert (first["weighted_percent"], first["grade"], first["grade_point"], first["passed"]) == (74.0, "P", 6.0, True)
    assert (first["status"], first["version"], first["course_offering_id"]) == ("computed", 1, o["id"])
    assert [(c["component_code"], c["final_marks"], c["max_marks"]) for c in first["components"]] == [
        ("END", 70.0, 100.0),
        ("INT", 80.0, 100.0),
    ]
    assert (rows[s2]["weighted_percent"], rows[s2]["grade"], rows[s2]["passed"]) == (4.0, "F", False)
    assert [c["absent"] for c in rows[s2]["components"]] == [True, False]  # END (absent) sorts first
    assert (rows[s3]["weighted_percent"], rows[s3]["passed"]) == (30.0, False)
    assert "exam_result.computed" in {e.action for e in audit_entries(org.id, cycle["id"])}


def test_moderation_counts_in_the_final_marks(client, org, h, cycle):
    s = uid()
    o = offering(client, org, h, cycle, [(s, 50, 50)])
    end = o["papers"]["END"]["id"]
    with session_for(org.id) as db:
        entry = db.scalars(
            repo.q(db, MarkEntryRow).where(
                MarkEntryRow.candidate_id.in_(
                    repo.q(db, CandidateRow).with_only_columns(CandidateRow.id).where(CandidateRow.exam_paper_id == end)
                )
            )
        ).one()
        entry.moderation_delta = D("10")
        db.commit()
    compute(client, h, cycle)
    assert results(client, h, cycle)[0]["weighted_percent"] == 56.0  # 0.4 * 50 + 0.6 * 60


def test_an_offering_that_cannot_be_computed_is_skipped_with_its_reason_and_writes_nothing(client, org, h, cycle):
    unlocked = offering(client, org, h, cycle, [(uid(), 50, 50)], lock=False)
    good = offering(client, org, h, cycle, [(uid(), 50, 50)])
    partial = offering(client, org, h, cycle, [(uid(), 50)], codes=("INT",))  # the END component has no paper
    summary = compute(client, h, cycle)
    assert (summary["course_offerings"], summary["results"]) == (1, 1)
    assert {s["course_offering_id"]: s["reason"] for s in summary["skipped"]} == {
        unlocked["id"]: "papers_not_locked",
        partial["id"]: "components_without_paper",
    }
    assert {r["course_offering_id"] for r in results(client, h, cycle)} == {good["id"]}
    unknown = uid()
    named = compute(client, h, cycle, unknown)
    assert named["skipped"] == [{"course_offering_id": unknown, "reason": "no_papers_in_cycle"}]


def test_a_student_who_is_not_a_candidate_of_every_paper_gets_no_result(client, org, h, cycle):
    whole, partial = uid(), uid()
    o = offering(client, org, h, cycle, [(whole, 50, 50)])
    with session_for(org.id) as db:  # a student with a candidacy for one paper only
        paper = o["papers"]["END"]
        db.add(
            CandidateRow(
                organisation_id=org.id,
                exam_cycle_id=cycle["id"],
                exam_paper_id=paper["id"],
                course_offering_id=o["id"],
                student_id=partial,
                eligibility_status="eligible",
                eligibility_reasons=[],
            )
        )
        db.commit()
    compute(client, h, cycle)
    assert [r["student_id"] for r in results(client, h, cycle)] == [whole]


def test_a_gap_in_the_grading_bands_skips_the_offering_rather_than_guessing(client, org, h):
    gap = [
        {"min_percent": 0, "max_percent": 39, "grade": "F", "grade_point": 0, "is_pass": False},
        {"min_percent": 41, "max_percent": 100, "grade": "P", "grade_point": 6, "is_pass": True},
    ]
    scheme = make_grading(client, h, "gapped", gap)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    gapped = make_cycle(client, h)
    set_row(org.id, ExamCycleRow, gapped["id"], status="evaluation")
    o = offering(client, org, h, gapped, [(uid(), 40, 40)])  # 40%: between the bands
    summary = compute(client, h, gapped)
    assert (summary["course_offerings"], summary["results"]) == (0, 0)
    assert summary["skipped"] == [{"course_offering_id": o["id"], "reason": "no_grading_band"}]
    assert results(client, h, gapped) == []


def test_recomputing_replaces_computed_results_in_place_and_drops_students_who_left(client, org, h, cycle):
    stays, leaves = uid(), uid()
    o = offering(client, org, h, cycle, [(stays, 50, 50), (leaves, 50, 50)])
    compute(client, h, cycle)
    first = by_student(results(client, h, cycle))
    with session_for(org.id) as db:  # a correction of the stored marks, and one candidacy lost
        for candidate in db.scalars(
            repo.q(db, CandidateRow).where(
                CandidateRow.student_id == leaves, CandidateRow.exam_paper_id == o["papers"]["END"]["id"]
            )
        ):
            candidate.eligibility_status = "ineligible"
        entry = db.scalars(
            repo.q(db, MarkEntryRow).where(
                MarkEntryRow.candidate_id.in_(
                    repo.q(db, CandidateRow).with_only_columns(CandidateRow.id).where(CandidateRow.student_id == stays)
                ),
                MarkEntryRow.marks_obtained == 50,
            )
        ).first()
        entry.marks_obtained = D("100")
        db.commit()
    again = compute(client, h, cycle)
    assert again["results"] == 1
    now = by_student(results(client, h, cycle))
    assert list(now) == [stays] and now[stays]["id"] == first[stays]["id"]  # the same row, updated, not a second one
    assert now[stays]["weighted_percent"] != first[stays]["weighted_percent"]
    superseded = results(client, h, cycle, include_superseded="true", status="superseded")
    assert [r["student_id"] for r in superseded] == [leaves]  # kept, not deleted


def test_results_that_are_already_approved_are_not_recomputed(client, org, h, cycle):
    o = offering(client, org, h, cycle, [(uid(), 50, 50)])
    compute(client, h, cycle)
    ok(client.post(url(cycle, "approve-department"), headers=h))
    again = compute(client, h, cycle)
    assert again["skipped"] == [{"course_offering_id": o["id"], "reason": "results_already_approved"}]
    assert results(client, h, cycle)[0]["status"] == "department_approved"


def test_the_cycle_must_be_in_evaluation(client, org, h, cycle):
    offering(client, org, h, cycle, [(uid(), 50, 50)])
    set_row(org.id, ExamCycleRow, cycle["id"], status="in_progress")
    for action in ("compute", "approve-department", "approve", "publish"):
        body = err(client.post(url(cycle, action), headers=h), 409, "cycle_not_in_evaluation")
        assert body["details"]["status"] == "in_progress", action
    set_row(org.id, ExamCycleRow, cycle["id"], status="results_published")
    for action in ("compute", "approve-department", "approve"):
        err(client.post(url(cycle, action), headers=h), 409, "cycle_results_published")
    assert ok(client.post(url(cycle, "publish"), headers=h))["results"] == 0  # a retried publication is not a conflict
    set_row(org.id, ExamCycleRow, cycle["id"], status="closed")
    err(client.post(url(cycle, "publish"), headers=h), 409, "cycle_results_published")


def test_a_malformed_selection_is_a_400_and_an_unknown_cycle_a_404(client, org, h, cycle):
    for body in ({"course_offering_ids": "x"}, {"course_offering_ids": ["nope"]}, {"other": 1}):
        err(client.post(url(cycle, "compute"), json=body, headers=h), 400, _code(client, h, cycle, body))
    missing = f"{BASE}/exam-cycles/{uid()}/results/compute"
    err(client.post(missing, headers=h), 404, "exam_cycle_not_found")
    err(client.post(f"{BASE}/exam-cycles/not-a-uuid/results/compute", headers=h), 400, "invalid_id")


def _code(client, h, cycle, body) -> str:
    return client.post(url(cycle, "compute"), json=body, headers=h).json()["detail"]["code"]


# ---------------------------------------------------------------- approval and publication


def test_the_stages_run_in_order_and_each_records_who_and_when(client, org, h, cycle):
    s = uid()
    o = offering(client, org, h, cycle, [(s, 50, 50)])
    compute(client, h, cycle)
    err(
        client.post(url(cycle, "approve"), json={"course_offering_ids": [o["id"]]}, headers=h),
        409,
        "invalid_status_transition",
    )
    err(
        client.post(url(cycle, "publish"), json={"course_offering_ids": [o["id"]]}, headers=h),
        409,
        "invalid_status_transition",
    )
    department = ok(client.post(url(cycle, "approve-department"), headers=h))
    assert department == {"exam_cycle_id": cycle["id"], "course_offerings": 1, "results": 1}
    assert results(client, h, cycle)[0]["status"] == "department_approved"
    err(
        client.post(url(cycle, "publish"), json={"course_offering_ids": [o["id"]]}, headers=h),
        409,
        "invalid_status_transition",
    )
    approved = ok(client.post(url(cycle, "approve"), headers=h))
    assert approved["results"] == 1
    row = results(client, h, cycle)[0]
    assert row["status"] == "approved" and row["approved_by"] is not None and row["published_at"] is None
    with session_for(org.id) as db:
        stored = db.get(ResultRow, row["id"])
        assert stored.department_approved_by and stored.department_approved_at and stored.approved_at
    published = ok(client.post(url(cycle, "publish"), headers=h))
    assert published["results"] == 1
    assert results(client, h, cycle)[0]["status"] == "published"
    assert sorted(e.action for e in audit_entries(org.id, row["id"])) == sorted(
        ["exam_result.department_approved", "exam_result.approved", "exam_result.published"]
    )


def test_a_retry_changes_nothing_and_says_so(client, org, h, cycle):
    o = offering(client, org, h, cycle, [(uid(), 50, 50)])
    compute(client, h, cycle)
    named = {"course_offering_ids": [o["id"]]}
    ok(client.post(url(cycle, "approve-department"), json=named, headers=h))
    again = ok(client.post(url(cycle, "approve-department"), json=named, headers=h))
    assert again["results"] == 0 and again["skipped"] == [
        {"course_offering_id": o["id"], "reason": "already_department_approved"}
    ]
    assert ok(client.post(url(cycle, "approve-department"), headers=h))["results"] == 0  # nothing named: nothing to do
    through = len(audit_entries(org.id))
    ok(client.post(url(cycle, "approve-department"), json=named, headers=h))
    assert len(audit_entries(org.id)) == through  # and nothing is audited twice
    ok(client.post(url(cycle, "approve"), headers=h))
    ok(client.post(url(cycle, "publish"), headers=h))
    events = outbox("examinations.result.published", org.id)
    again = ok(client.post(url(cycle, "publish"), json=named, headers=h))
    assert again["results"] == 0 and again["skipped"][0]["reason"] == "already_published"
    assert len(outbox("examinations.result.published", org.id)) == len(events) == 1  # not published twice


def test_a_department_head_alone_cannot_approve_or_read_the_organisations_results(client, org, h, cycle):
    offering(client, org, h, cycle, [(uid(), 50, 50)])
    compute(client, h, cycle)
    _, head = org.user(HEAD)
    err(client.post(url(cycle, "approve-department"), headers=head), 403, "forbidden")  # Q13: no known department
    err(client.post(url(cycle, "approve"), headers=head), 403, "forbidden")
    err(client.get(f"{BASE}/results", headers=head), 403, "forbidden")
    assert results(client, h, cycle)[0]["status"] == "computed"
    _, faculty = org.user(FACULTY)
    for call in (
        client.post(url(cycle, "compute"), headers=faculty),
        client.post(url(cycle, "publish"), headers=faculty),
        client.get(f"{BASE}/results", headers=faculty),
    ):
        assert call.status_code == 403


def test_publishing_sends_one_event_per_student_with_the_credit_weighted_average_and_closes_the_cycle(
    client, org, h, cycle
):
    s1, s2 = uid(), uid()
    a = offering(client, org, h, cycle, [(s1, 80, 70), (s2, 10, 10)])
    b = offering(client, org, h, cycle, [(s1, 100, 100)])
    add_ref(org, a["id"], 4, "CS101")
    add_ref(org, b["id"], 2, "CS102")
    compute(client, h, cycle)
    through_approval(client, h, cycle)
    summary = ok(client.post(url(cycle, "publish"), headers=h))
    assert (summary["course_offerings"], summary["results"]) == (2, 3)
    events = {e["student_id"]: e for e in outbox("examinations.result.published", org.id)}
    assert set(events) == {s1, s2}
    first = events[s1]
    assert first["exam_cycle_id"] == cycle["id"] and first["academic_period_id"] == cycle["academic_period_id"]
    assert sorted(c["course_offering_id"] for c in first["courses"]) == sorted([a["id"], b["id"]])
    assert {c["grade"] for c in first["courses"]} == {"P"} and first["published_at"].startswith("2026-11-05")
    assert first["grade_point_average"] == 6.0  # (6 * 4 + 6 * 2) / 6
    assert len(events[s2]["courses"]) == 1 and events[s2]["grade_point_average"] == 0.0
    fetched = ok(client.get(f"{BASE}/exam-cycles/{cycle['id']}", headers=h))
    assert fetched["status"] == "results_published"


def test_the_cycle_stays_in_evaluation_until_every_offering_is_published(client, org, h, cycle):
    a = offering(client, org, h, cycle, [(uid(), 50, 50)])
    b = offering(client, org, h, cycle, [(uid(), 50, 50)])
    compute(client, h, cycle)
    through_approval(client, h, cycle, a["id"])
    ok(client.post(url(cycle, "publish"), json={"course_offering_ids": [a["id"]]}, headers=h))
    assert ok(client.get(f"{BASE}/exam-cycles/{cycle['id']}", headers=h))["status"] == "evaluation"
    through_approval(client, h, cycle, b["id"])
    ok(client.post(url(cycle, "publish"), json={"course_offering_ids": [b["id"]]}, headers=h))
    assert ok(client.get(f"{BASE}/exam-cycles/{cycle['id']}", headers=h))["status"] == "results_published"


def test_an_offering_whose_papers_are_not_all_locked_keeps_the_cycle_open(client, org, h, cycle):
    done = offering(client, org, h, cycle, [(uid(), 50, 50)])
    offering(client, org, h, cycle, [(uid(), 50, 50)], lock=False)
    compute(client, h, cycle)
    through_approval(client, h, cycle)
    ok(client.post(url(cycle, "publish"), json={"course_offering_ids": [done["id"]]}, headers=h))
    assert ok(client.get(f"{BASE}/exam-cycles/{cycle['id']}", headers=h))["status"] == "evaluation"


def test_an_unknown_credit_leaves_the_average_unknown(client, org, h, cycle):
    s = uid()
    o = offering(client, org, h, cycle, [(s, 50, 50)])
    add_ref(org, o["id"], None)
    compute(client, h, cycle)
    through_approval(client, h, cycle)
    ok(client.post(url(cycle, "publish"), headers=h))
    assert outbox("examinations.result.published", org.id)[0]["grade_point_average"] is None


# ---------------------------------------------------------------- reads


def test_listing_filters_pages_and_hides_superseded_versions_by_default(client, org, h, cycle):
    s1, s2 = uid(), uid()
    a = offering(client, org, h, cycle, [(s1, 80, 70), (s2, 10, 10)])
    compute(client, h, cycle)
    assert len(results(client, h, cycle)) == 2
    assert [r["student_id"] for r in results(client, h, cycle, student_id=s1)] == [s1]
    assert len(results(client, h, cycle, course_offering_id=a["id"])) == 2
    assert results(client, h, cycle, course_offering_id=uid()) == []
    assert len(results(client, h, cycle, status="computed")) == 2 and results(client, h, cycle, status="approved") == []
    page = ok(client.get(f"{BASE}/results", params={"exam_cycle_id": cycle["id"], "limit": 1, "offset": 1}, headers=h))
    assert len(page["items"]) == 1 and page["total"] == 2
    for query in ({"status": "done"}, {"student_id": "x"}, {"exam_cycle_id": "x"}):
        assert client.get(f"{BASE}/results", params=query, headers=h).status_code == 400, query
    assert client.get(f"{BASE}/results").status_code == 401


def test_a_result_carries_the_course_facts_when_the_offering_is_known(client, org, h, cycle):
    o = offering(client, org, h, cycle, [(uid(), 50, 50)])
    add_ref(org, o["id"], 3, "CS999")
    compute(client, h, cycle)
    row = results(client, h, cycle)[0]
    assert (row["course_code"], row["course_title"], row["credits"]) == ("CS999", "CS999 title", 3.0)


def test_a_student_reads_only_their_own_published_results_by_cycle(client, org, other_org, h, cycle):
    mine, other = uid(), uid()
    a = offering(client, org, h, cycle, [(mine, 80, 70), (other, 10, 10)])
    add_ref(org, a["id"], 4)
    _, student = org.user(STUDENT, user_id=mine)
    compute(client, h, cycle)
    through_approval(client, h, cycle)
    assert ok(client.get(f"{BASE}/me/results", headers=student)) == {"items": []}  # approved is not yet visible
    ok(client.post(url(cycle, "publish"), headers=h))
    items = ok(client.get(f"{BASE}/me/results", headers=student))["items"]
    assert len(items) == 1
    group = items[0]
    assert group["exam_cycle_id"] == cycle["id"] and group["exam_cycle_name"] == cycle["name"]
    assert group["grade_point_average"] == 6.0
    assert [r["student_id"] for r in group["results"]] == [mine] and group["results"][0]["status"] == "published"
    assert ok(client.get(f"{BASE}/me/results", params={"exam_cycle_id": uid()}, headers=student)) == {"items": []}
    assert client.get(f"{BASE}/me/results", params={"exam_cycle_id": "x"}, headers=student).status_code == 400
    _, elsewhere = other_org.user(STUDENT, user_id=mine)  # the same user id in another organisation
    assert ok(client.get(f"{BASE}/me/results", headers=elsewhere)) == {"items": []}
    _, faculty = org.user(FACULTY)
    assert client.get(f"{BASE}/me/results", headers=faculty).status_code == 403
    assert client.get(f"{BASE}/me/results").status_code == 401


def test_another_organisation_sees_none_of_it(client, org, other_org, h, cycle):
    offering(client, org, h, cycle, [(uid(), 50, 50)])
    compute(client, h, cycle)
    outsider = other_org.controller()
    err(client.post(url(cycle, "compute"), headers=outsider), 404, "exam_cycle_not_found")
    err(client.post(url(cycle, "publish"), headers=outsider), 404, "exam_cycle_not_found")
    assert ok(client.get(f"{BASE}/results", params={"exam_cycle_id": cycle["id"]}, headers=outsider))["items"] == []
    row = results(client, h, cycle)[0]
    err(client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(60), headers=outsider), 404, "result_not_found")


# ---------------------------------------------------------------- revision


def _fix(marks, reason="a moderation error") -> dict:
    return {"reason": reason, "components": [{"component_code": "END", "final_marks": marks}]}


def published(client, org, h, cycle, students=None):
    s = uid()
    o = offering(client, org, h, cycle, students or [(s, 50, 50)])
    add_ref(org, o["id"], 4)
    compute(client, h, cycle)
    through_approval(client, h, cycle)
    ok(client.post(url(cycle, "publish"), headers=h))
    return s, o, results(client, h, cycle)[0]


def test_a_revision_makes_a_new_published_version_keeps_the_old_one_and_tells_consumers_once(client, org, h, cycle):
    s, o, row = published(client, org, h, cycle)
    assert (row["weighted_percent"], row["version"]) == (50.0, 1)
    revised = ok(client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(20), headers=h))
    assert revised["id"] != row["id"] and revised["version"] == 2 and revised["status"] == "published"
    assert revised["revision_reason"] == "a moderation error" and revised["weighted_percent"] == 32.0  # 0.4*50 + 0.6*20
    assert (revised["grade"], revised["passed"]) == ("F", False)
    assert [c["final_marks"] for c in revised["components"]] == [20.0, 50.0]
    assert revised["approved_by"] == row["approved_by"] and revised["published_at"] == row["published_at"]
    assert [r["id"] for r in results(client, h, cycle)] == [revised["id"]]
    both = results(client, h, cycle, include_superseded="true")
    assert [(r["version"], r["status"]) for r in both] == [(1, "superseded"), (2, "published")]
    assert len(outbox("examinations.result.published", org.id)) == 1  # not published again
    [event] = outbox("examinations.result.revised", org.id)
    assert (event["result_id"], event["previous_version"], event["version"]) == (revised["id"], 1, 2)
    assert event["previous"] == {"weighted_percent": 50.0, "grade": "P", "grade_point": 6.0, "passed": True}
    assert event["current"] == {"weighted_percent": 32.0, "grade": "F", "grade_point": 0.0, "passed": False}
    assert event["grade_point_average"] == 0.0 and event["reason"] == "a moderation error"
    assert event["student_id"] == s and event["course_offering_id"] == o["id"]
    entry = audit_entries(org.id, revised["id"])[-1]
    assert (entry.action, entry.reason) == ("exam_result.revised", "a moderation error")
    assert entry.before["version"] == 1 and entry.after["version"] == 2


def test_the_student_sees_only_the_current_version(client, org, h, cycle):
    s, _, row = published(client, org, h, cycle)
    ok(client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(90), headers=h))
    _, student = org.user(STUDENT, user_id=s)
    [group] = ok(client.get(f"{BASE}/me/results", headers=student))["items"]
    assert [r["version"] for r in group["results"]] == [2]


def test_only_the_current_published_version_is_revised(client, org, h, cycle):
    s, o, row = published(client, org, h, cycle)
    ok(client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(60), headers=h))
    err(client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(70), headers=h), 409, "result_not_published")
    other = offering(client, org, h, cycle, [(uid(), 50, 50)], lock=True)
    compute(client, h, cycle, other["id"])
    computed = next(r for r in results(client, h, cycle, status="computed"))
    err(client.post(f"{BASE}/results/{computed['id']}/revise", json=_fix(70), headers=h), 409, "result_not_published")


def test_a_revision_is_still_possible_once_the_cycle_is_closed(client, org, h, cycle):
    _, _, row = published(client, org, h, cycle)
    set_row(org.id, ExamCycleRow, cycle["id"], status="closed")
    assert ok(client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(80), headers=h))["version"] == 2


@pytest.mark.parametrize(
    ("body", "status", "code"),
    [
        ({"components": [{"component_code": "END", "final_marks": 60}]}, 400, "invalid_text"),
        ({"reason": "", "components": [{"component_code": "END", "final_marks": 60}]}, 400, "invalid_text"),
        ({"reason": "x" * 501, "components": [{"component_code": "END", "final_marks": 60}]}, 400, "text_too_long"),
        ({"reason": "x"}, 400, "missing_field"),
        ({"reason": "x", "components": []}, 400, "invalid_components"),
        ({"reason": "x", "components": [{"component_code": "END"}]}, 400, "invalid_components"),
        (
            {"reason": "x", "components": [{"component_code": "END", "final_marks": 60}], "extra": 1},
            400,
            "unknown_field",
        ),
        ({"reason": "x", "components": [{"component_code": "VIVA", "final_marks": 60}]}, 422, "unknown_component"),
        ({"reason": "x", "components": [{"component_code": "END", "final_marks": 101}]}, 422, "marks_out_of_range"),
    ],
)
def test_a_malformed_or_out_of_range_revision_changes_nothing(client, org, h, cycle, body, status, code):
    _, _, row = published(client, org, h, cycle)
    err(client.post(f"{BASE}/results/{row['id']}/revise", json=body, headers=h), status, code)
    assert [(r["version"], r["status"]) for r in results(client, h, cycle, include_superseded="true")] == [
        (1, "published")
    ]
    assert outbox("examinations.result.revised", org.id) == []


def test_a_revision_needs_its_key_and_a_known_result(client, org, h, cycle):
    _, _, row = published(client, org, h, cycle)
    for role in (HEAD, FACULTY, STUDENT):
        _, headers = org.user(role)
        assert client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(60), headers=headers).status_code == 403
    assert client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(60)).status_code == 401
    err(client.post(f"{BASE}/results/{uid()}/revise", json=_fix(60), headers=h), 404, "result_not_found")
    err(client.post(f"{BASE}/results/x/revise", json=_fix(60), headers=h), 400, "invalid_id")


def test_no_result_row_is_ever_deleted(client, org, h, cycle):
    _, _, row = published(client, org, h, cycle)
    ok(client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(60), headers=h))
    with session_for(org.id) as db:
        assert db.get(ResultRow, row["id"]).status == "superseded"
        assert len(list(db.scalars(repo.q(db, ResultRow)))) >= 2


def test_the_controller_is_the_role_that_runs_every_stage(client, org, h, cycle):
    # the stages are keyed by the contract's permissions; the controller holds them all (permissions.yaml)
    _, controller = org.user(CONTROLLER)
    offering(client, org, h, cycle, [(uid(), 50, 50)])
    assert compute(client, controller, cycle)["results"] == 1
    assert ok(client.post(url(cycle, "approve-department"), headers=controller))["results"] == 1
    assert ok(client.post(url(cycle, "approve"), headers=controller))["results"] == 1
    assert ok(client.post(url(cycle, "publish"), headers=controller))["results"] == 1


def test_the_bodies_and_errors_match_the_contract(client, org, h, cycle):
    s = uid()
    offering(client, org, h, cycle, [(s, 50, 50)])
    for operation_id, call in (
        ("computeResults", client.post(url(cycle, "compute"), headers=h)),
        ("approveResultsDepartment", client.post(url(cycle, "approve-department"), headers=h)),
        ("approveResults", client.post(url(cycle, "approve"), headers=h)),
        ("publishResults", client.post(url(cycle, "publish"), headers=h)),
    ):
        assert call.status_code == 200, (operation_id, call.text)
        check(call.json(), SCHEMAS["ResultActionSummary"])
        assert "200" in operation(operation_id)["responses"]
    listed = client.get(f"{BASE}/results", params={"exam_cycle_id": cycle["id"]}, headers=h)
    for item in listed.json()["items"]:
        check(item, SCHEMAS["Result"])
    row = listed.json()["items"][0]
    revised = client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(60), headers=h)
    check(revised.json(), SCHEMAS["Result"])
    _, student = org.user(STUDENT, user_id=s)
    for item in client.get(f"{BASE}/me/results", headers=student).json()["items"]:
        check(item, SCHEMAS["StudentCycleResult"])
    for call, status, operation_id in (
        (client.post(url(cycle, "compute"), headers=org.user(FACULTY)[1]), 403, None),
        (client.post(f"{BASE}/exam-cycles/{uid()}/results/compute", headers=h), 404, "computeResults"),
        (client.post(url(cycle, "compute"), json={"x": 1}, headers=h), 400, "computeResults"),
        (client.post(url(cycle, "approve"), headers=org.user(HEAD)[1]), 403, "approveResults"),
        (client.post(f"{BASE}/results/{row['id']}/revise", json=_fix(60), headers=h), 409, "reviseResult"),
        (client.post(f"{BASE}/results/{revised.json()['id']}/revise", json=_fix(500), headers=h), 422, "reviseResult"),
    ):
        assert call.status_code == status, (operation_id, call.text)
        check(call.json()["detail"], SCHEMAS["ErrorResponse"])
        if operation_id:
            assert str(status) in operation(operation_id)["responses"], (operation_id, status)
