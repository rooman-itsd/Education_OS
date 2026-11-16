"""listExamPapers, createExamPapers, getExamPaper, updateExamPaper."""

from pathlib import Path

import pytest
import yaml

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    HEAD,
    STUDENT,
    VIEWER,
    all_outbox,
    audit_entries,
    component,
    err,
    make_assessment,
    make_cycle,
    make_grading,
    make_papers,
    make_session,
    ok,
    session_for,
    set_row,
    uid,
)
from eos_core.db import engine  # noqa: E402
from eos_examinations.infrastructure.models import ExamCycleRow, ExamPaperRow, OfferingRef  # noqa: E402
from sqlalchemy import event  # noqa: E402

URL = f"{BASE}/papers"


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


def create(client, headers, cycle_id, offering_id, codes, **over):
    body = {"exam_cycle_id": cycle_id, "course_offering_id": offering_id, "component_codes": codes, **over}
    return client.post(URL, json=body, headers=headers)


def test_the_operations_need_their_keys(client, org, h, cycle):
    _, head = org.user(HEAD)
    _, viewer = org.user(VIEWER)
    _, faculty = org.user(FACULTY)
    _, student = org.user(STUDENT)  # no paper key
    paper = make_papers(client, h, cycle["id"])[0]
    assert client.get(URL).status_code == 401
    assert client.post(URL, json={}).status_code == 401
    for headers in (head, viewer, faculty):  # paper:read
        assert client.get(URL, headers=headers).status_code == 200
        assert client.get(f"{URL}/{paper['id']}", headers=headers).status_code == 200
    assert client.get(URL, headers=student).status_code == 403
    assert client.get(f"{URL}/{paper['id']}", headers=student).status_code == 403
    for headers in (head, viewer, faculty, student):  # reading is not managing
        for r in (
            client.post(URL, json={}, headers=headers),
            client.patch(f"{URL}/{paper['id']}", json={"duration_minutes": 5}, headers=headers),
        ):
            assert r.status_code == 403
            assert r.json()["detail"]["code"] == "forbidden"


def test_create_makes_one_draft_paper_per_listed_component_with_the_components_marks(client, org, h, cycle):
    offering = uid()
    papers = make_papers(client, h, cycle["id"], offering, ["END"], duration_minutes=90)
    assert len(papers) == 1
    paper = papers[0]
    assert paper == {
        "id": paper["id"],
        "organisation_id": org.id,
        "exam_cycle_id": cycle["id"],
        "course_offering_id": offering,
        "assessment_component_id": paper["assessment_component_id"],
        "component_code": "END",
        "max_marks": 100.0,
        "duration_minutes": 90,
        "exam_session_id": None,
        "status": "draft",
    }
    assert ok(client.get(f"{URL}/{paper['id']}", headers=h)) == paper
    # the other component can be added later; the first is not repeated
    more = make_papers(client, h, cycle["id"], offering, ["INT"])
    assert [p["component_code"] for p in more] == ["INT"]
    assert ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}", headers=h))["total"] == 2


def test_the_paper_uses_the_active_schemes_component_not_a_draft_versions(client, h, cycle):
    offering = uid()
    v1 = make_assessment(client, h, offering, [component("END", 100, max_marks=50)])
    ok(client.post(f"{BASE}/assessment-schemes/{v1['id']}/activate", headers=h))
    make_assessment(client, h, offering, [component("END", 100, max_marks=80)])  # a draft v2: ignored
    assert make_papers(client, h, cycle["id"], offering, ["END"])[0]["max_marks"] == 50.0


@pytest.mark.parametrize(
    ("change", "code", "field"),
    [
        ({"exam_cycle_id": "x"}, "invalid_id", "exam_cycle_id"),
        ({"course_offering_id": "x"}, "invalid_id", "course_offering_id"),
        ({"component_codes": "END"}, "invalid_body", "component_codes"),
        ({"component_codes": []}, "no_papers", "papers"),
        ({"component_codes": ["END", "END"]}, "duplicate_component", "papers[1].component_code"),
        ({"duration_minutes": 0}, "below_minimum", "duration_minutes"),
        ({"duration_minutes": "90"}, "invalid_integer", "duration_minutes"),
        ({"duration_minutes": True}, "invalid_integer", "duration_minutes"),
        ({"max_marks": 10}, "unknown_field", "max_marks"),
        ({"status": "locked"}, "unknown_field", "status"),
    ],
)
def test_invalid_input_is_refused_and_creates_nothing(client, org, h, cycle, change, code, field):
    offering = uid()
    make_papers(client, h, cycle["id"], offering, ["INT"])  # gives the offering its active scheme
    before = ok(client.get(URL, headers=h))["total"]
    body = {"exam_cycle_id": cycle["id"], "course_offering_id": offering, "component_codes": ["END"], **change}
    r = client.post(URL, json=body, headers=h)
    detail = err(r, 400, code)
    assert detail["details"]["field"] == field
    assert ok(client.get(URL, headers=h))["total"] == before


@pytest.mark.parametrize("missing", ["exam_cycle_id", "course_offering_id", "component_codes"])
def test_a_missing_field_is_400(client, h, cycle, missing):
    body = {"exam_cycle_id": cycle["id"], "course_offering_id": uid(), "component_codes": ["END"]}
    del body[missing]
    assert err(client.post(URL, json=body, headers=h), 400, "missing_field")["details"]["field"] == missing


def test_unprocessable_requests_are_422(client, org, other_org, h, cycle):
    offering = uid()
    err(create(client, h, uid(), offering, ["END"]), 422, "unknown_exam_cycle")
    err(create(client, h, cycle["id"], offering, ["END"]), 422, "scheme_not_active")  # no scheme at all
    make_assessment(client, h, offering)  # a draft only
    err(create(client, h, cycle["id"], offering, ["END"]), 422, "scheme_not_active")
    active = make_papers(client, h, cycle["id"], uid())  # another offering with an active scheme
    other = active[0]["course_offering_id"]
    detail = err(create(client, h, cycle["id"], other, ["NOPE"]), 422, "unknown_component")
    assert detail["details"]["field"] == "papers[0].component_code"
    # another organisation's scheme and cycle are invisible
    other_h = other_org.controller()
    foreign = uid()
    scheme = make_assessment(client, other_h, foreign)
    ok(client.post(f"{BASE}/assessment-schemes/{scheme['id']}/activate", headers=other_h))
    err(create(client, h, cycle["id"], foreign, ["END"]), 422, "scheme_not_active")
    err(create(client, other_h, cycle["id"], foreign, ["END"]), 422, "unknown_exam_cycle")


def test_a_component_has_one_paper_per_cycle_and_a_second_cycle_may_have_its_own(client, org, h, cycle):
    offering = uid()
    make_papers(client, h, cycle["id"], offering, ["END"])
    err(create(client, h, cycle["id"], offering, ["END"]), 409, "paper_exists")
    err(create(client, h, cycle["id"], offering, ["INT", "END"]), 409, "paper_exists")
    assert ok(client.get(URL, headers=h))["total"] == 1  # the INT paper of the refused request was not kept
    second = make_cycle(client, h)
    assert make_papers(client, h, second["id"], offering, ["END"])[0]["status"] == "draft"


def test_papers_can_only_be_created_while_the_cycle_is_draft_or_scheduled(client, org, h, cycle):
    offering = uid()
    make_papers(client, h, cycle["id"], offering, ["INT"])
    set_row(org.id, ExamCycleRow, cycle["id"], status="in_progress")
    detail = err(create(client, h, cycle["id"], offering, ["END"]), 409, "cycle_not_configurable")
    assert detail["details"]["status"] == "in_progress"


def test_list_filters_and_pages(client, org, h, cycle):
    other_cycle = make_cycle(client, h)
    a, b = uid(), uid()
    make_papers(client, h, cycle["id"], a)
    make_papers(client, h, cycle["id"], b, ["END"])
    make_papers(client, h, other_cycle["id"], a, ["END"])
    assert ok(client.get(URL, headers=h))["total"] == 4
    assert ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}", headers=h))["total"] == 3
    assert ok(client.get(f"{URL}?course_offering_id={a}", headers=h))["total"] == 3
    assert ok(client.get(f"{URL}?course_offering_id={a}&exam_cycle_id={cycle['id']}", headers=h))["total"] == 2
    page = ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}&limit=2&offset=2", headers=h))
    assert page["total"] == 3 and len(page["items"]) == 1
    assert ok(client.get(f"{URL}?status=draft", headers=h))["total"] == 4
    assert ok(client.get(f"{URL}?status=locked", headers=h))["total"] == 0
    assert ok(client.get(f"{URL}?department_id={uid()}", headers=h)) == {
        "items": [],
        "total": 0,
    }  # no offering has that department
    err(client.get(f"{URL}?status=bogus", headers=h), 400, "invalid_choice")
    err(client.get(f"{URL}?department_id=x", headers=h), 400, "invalid_id")
    err(client.get(f"{URL}?exam_cycle_id=x", headers=h), 400, "invalid_id")


def test_update_changes_a_drafts_duration(client, org, h, cycle):
    paper = make_papers(client, h, cycle["id"])[0]
    updated = ok(client.patch(f"{URL}/{paper['id']}", json={"duration_minutes": 150}, headers=h))
    assert updated == {**paper, "duration_minutes": 150}
    assert ok(client.get(f"{URL}/{paper['id']}", headers=h)) == updated
    before = len(audit_entries(org.id, paper["id"]))
    assert ok(client.patch(f"{URL}/{paper['id']}", json={}, headers=h)) == updated  # nothing to change
    assert ok(client.patch(f"{URL}/{paper['id']}", json={"duration_minutes": 150}, headers=h)) == updated
    assert len(audit_entries(org.id, paper["id"])) == before


def test_a_paper_has_no_title_until_one_is_set_and_update_stores_and_returns_it(client, org, h, cycle):
    paper = make_papers(client, h, cycle["id"])[0]
    assert "title" not in paper  # the contract's title is a string, so an untitled paper omits it
    titled = ok(client.patch(f"{URL}/{paper['id']}", json={"title": "  Paper I: Algorithms  "}, headers=h))
    assert titled == {**paper, "title": "Paper I: Algorithms"}
    assert ok(client.get(f"{URL}/{paper['id']}", headers=h)) == titled
    assert [
        p["title"] for p in ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}", headers=h))["items"] if "title" in p
    ] == ["Paper I: Algorithms"]
    both = ok(client.patch(f"{URL}/{paper['id']}", json={"title": "Paper 1", "duration_minutes": 90}, headers=h))
    assert (both["title"], both["duration_minutes"]) == ("Paper 1", 90)
    entries = [e for e in audit_entries(org.id, paper["id"]) if e.action == "exam_paper.updated"]
    assert {str(e.after) for e in entries} == {
        "{'title': 'Paper I: Algorithms'}",
        "{'title': 'Paper 1', 'duration_minutes': 90}",
    }
    before = len(audit_entries(org.id, paper["id"]))
    assert ok(client.patch(f"{URL}/{paper['id']}", json={"title": "Paper 1"}, headers=h)) == both  # unchanged: no entry
    assert len(audit_entries(org.id, paper["id"])) == before


def test_a_title_is_scoped_to_its_paper_and_organisation(client, org, other_org, h, cycle):
    first, second = make_papers(client, h, cycle["id"])
    ok(client.patch(f"{URL}/{first['id']}", json={"title": "Mine"}, headers=h))
    assert "title" not in ok(client.get(f"{URL}/{second['id']}", headers=h))
    other_h = other_org.controller()
    err(client.patch(f"{URL}/{first['id']}", json={"title": "Hijacked"}, headers=other_h), 404, "exam_paper_not_found")
    assert ok(client.get(f"{URL}/{first['id']}", headers=h))["title"] == "Mine"


def test_a_title_is_refused_on_a_paper_that_is_not_draft_or_in_a_closed_cycle(client, org, h, cycle):
    first, second = make_papers(client, h, cycle["id"])
    make_session(client, h, cycle["id"], [first["id"]])
    err(client.patch(f"{URL}/{first['id']}", json={"title": "x"}, headers=h), 409, "paper_not_draft")
    set_row(org.id, ExamCycleRow, cycle["id"], status="evaluation")
    err(client.patch(f"{URL}/{second['id']}", json={"title": "x"}, headers=h), 409, "cycle_not_configurable")
    assert "title" not in ok(client.get(f"{URL}/{second['id']}", headers=h))


@pytest.mark.parametrize(
    ("patch", "code"),
    [
        ({"duration_minutes": 0}, "below_minimum"),
        ({"duration_minutes": 1.5}, "invalid_integer"),
        ({"duration_minutes": None}, "invalid_integer"),
        ({"title": ""}, "invalid_text"),  # the contract's title is a string: replaced, never cleared
        ({"title": "  "}, "invalid_text"),
        ({"title": None}, "invalid_text"),
        ({"title": 5}, "invalid_text"),
        ({"title": "t" * 201}, "text_too_long"),
        ({"max_marks": 5}, "unknown_field"),
        ({"status": "locked"}, "unknown_field"),
        ({"exam_cycle_id": uid()}, "unknown_field"),
    ],
)
def test_an_invalid_update_is_400_and_changes_nothing(client, h, cycle, patch, code):
    paper = make_papers(client, h, cycle["id"])[0]
    err(client.patch(f"{URL}/{paper['id']}", json=patch, headers=h), 400, code)
    assert ok(client.get(f"{URL}/{paper['id']}", headers=h)) == paper


def test_only_a_draft_paper_of_a_configurable_cycle_can_be_edited(client, org, h, cycle):
    first, second = make_papers(client, h, cycle["id"])
    make_session(client, h, cycle["id"], [first["id"]])  # the paper becomes scheduled
    detail = err(client.patch(f"{URL}/{first['id']}", json={"duration_minutes": 5}, headers=h), 409, "paper_not_draft")
    assert detail["details"]["status"] == "scheduled"
    set_row(org.id, ExamPaperRow, second["id"], status="marks_entry")
    err(client.patch(f"{URL}/{second['id']}", json={"duration_minutes": 5}, headers=h), 409, "paper_not_draft")
    third = make_papers(client, h, cycle["id"], uid())[0]
    set_row(org.id, ExamCycleRow, cycle["id"], status="evaluation")
    err(client.patch(f"{URL}/{third['id']}", json={"duration_minutes": 5}, headers=h), 409, "cycle_not_configurable")


def test_a_missing_paper_is_404(client, h):
    err(client.get(f"{URL}/{uid()}", headers=h), 404, "exam_paper_not_found")
    err(client.patch(f"{URL}/{uid()}", json={"duration_minutes": 5}, headers=h), 404, "exam_paper_not_found")
    err(client.get(f"{URL}/not-a-uuid", headers=h), 404, "exam_paper_not_found")


def test_each_organisation_sees_and_changes_only_its_own_papers(client, org, other_org, h, cycle):
    other_h = other_org.controller()
    g = make_grading(client, other_h)
    ok(client.post(f"{BASE}/grading-schemes/{g['id']}/set-default", headers=other_h))
    offering = uid()
    mine = make_papers(client, h, cycle["id"], offering)
    theirs = make_papers(client, other_h, make_cycle(client, other_h)["id"], offering)  # the same offering id
    assert {p["organisation_id"] for p in mine} == {org.id} and {p["organisation_id"] for p in theirs} == {other_org.id}
    assert {p["id"] for p in ok(client.get(URL, headers=h))["items"]} == {p["id"] for p in mine}
    assert ok(client.get(URL, headers=other_h))["total"] == 2
    err(client.get(f"{URL}/{theirs[0]['id']}", headers=h), 404, "exam_paper_not_found")
    err(client.patch(f"{URL}/{theirs[0]['id']}", json={"duration_minutes": 5}, headers=h), 404, "exam_paper_not_found")
    assert ok(client.get(f"{URL}/{theirs[0]['id']}", headers=other_h))["duration_minutes"] is None
    assert audit_entries(org.id, theirs[0]["id"]) == []


def test_each_paper_is_audited_with_the_actor_and_publishes_no_event(client, org, h, cycle):
    user, headers = org.user("examinations-controller")
    offering = uid()
    papers = make_papers(client, headers, cycle["id"], offering, ["INT", "END"])
    ok(client.patch(f"{URL}/{papers[0]['id']}", json={"duration_minutes": 60}, headers=headers))
    ok(client.patch(f"{URL}/{papers[0]['id']}", json={"duration_minutes": 75}, headers=headers))
    entries = audit_entries(org.id, papers[0]["id"])
    assert sorted(e.action for e in entries) == ["exam_paper.created", "exam_paper.updated", "exam_paper.updated"]
    assert {e.actor for e in entries} == {user} and {e.entity_type for e in entries} == {"exam_paper"}
    created = next(e for e in entries if e.action == "exam_paper.created")
    assert created.before is None and created.after["course_offering_id"] == offering
    changes = sorted(
        (
            (e.before["duration_minutes"], e.after["duration_minutes"])
            for e in entries
            if e.action == "exam_paper.updated"
        ),
        key=str,
    )
    assert changes == [(60, 75), (None, 60)]
    assert len(audit_entries(org.id, papers[1]["id"])) == 1
    assert all_outbox(org.id) == ["examinations.exam-cycle.created"]  # the fixture's cycle; papers publish no event


def test_a_scheme_used_by_papers_can_be_superseded_without_touching_them(client, h, cycle):
    offering = uid()
    papers = make_papers(client, h, cycle["id"], offering, ["END"])
    v2 = make_assessment(client, h, offering, [component("END", 100, max_marks=30)])
    ok(client.post(f"{BASE}/assessment-schemes/{v2['id']}/activate", headers=h))
    assert ok(client.get(f"{URL}/{papers[0]['id']}", headers=h))["max_marks"] == 100.0


# ---------------------------------------------------------------- course_code, course_title, department_id (offering_ref)

OFFERING_FIELDS = ("course_code", "course_title", "department_id")
CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"


def add_offering(org_id: str, offering_id: str, **fields) -> None:
    """A row of the offering read model. Defaults describe a known offering; pass `None` for what the row lacks."""
    values = {
        "course_id": uid(),
        "academic_period_id": uid(),
        "course_code": "CS101",
        "course_title": "Programming",
        "credits": 4,
        "department_id": uid(),
        **fields,
    }
    with session_for(org_id) as db:
        db.add(OfferingRef(organisation_id=org_id, course_offering_id=offering_id, **values))
        db.commit()


def offering_facts(paper: dict) -> dict:
    return {k: paper[k] for k in OFFERING_FIELDS if k in paper}


def test_a_paper_with_no_offering_row_omits_the_three_fields_and_changes_nothing_else(client, org, h, cycle):
    paper = make_papers(client, h, cycle["id"], codes=["END"])[0]
    assert not set(OFFERING_FIELDS) & set(paper)  # omitted, never null or empty
    for body in (
        ok(client.get(f"{URL}/{paper['id']}", headers=h)),
        ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}", headers=h))["items"][0],
    ):
        assert body == paper


def test_a_populated_offering_row_is_served_on_create_get_list_and_update(client, org, h, cycle):
    offering, department = uid(), uid()
    add_offering(org.id, offering, course_code="CS101", course_title="Programming", department_id=department)
    expected = {"course_code": "CS101", "course_title": "Programming", "department_id": department}
    created = make_papers(client, h, cycle["id"], offering, ["END"])[0]
    assert offering_facts(created) == expected
    assert ok(client.get(f"{URL}/{created['id']}", headers=h)) == created
    [listed] = ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}", headers=h))["items"]
    assert listed == created
    updated = ok(client.patch(f"{URL}/{created['id']}", json={"duration_minutes": 120}, headers=h))
    assert updated == {**created, "duration_minutes": 120} and offering_facts(updated) == expected
    # every field the paper had without the read model is unchanged
    assert {k: v for k, v in created.items() if k not in OFFERING_FIELDS} == {
        "id": created["id"],
        "organisation_id": org.id,
        "exam_cycle_id": cycle["id"],
        "course_offering_id": offering,
        "assessment_component_id": created["assessment_component_id"],
        "component_code": "END",
        "max_marks": 100.0,
        "duration_minutes": None,
        "exam_session_id": None,
        "status": "draft",
    }


def test_a_row_only_a_status_change_created_serves_nothing(client, org, h, cycle):
    offering = uid()
    add_offering(
        org.id,
        offering,
        course_id=None,
        academic_period_id=None,
        course_code=None,
        course_title=None,
        credits=None,
        department_id=None,
        status="open",
    )
    paper = make_papers(client, h, cycle["id"], offering, ["END"])[0]
    assert not set(OFFERING_FIELDS) & set(paper)
    assert not set(OFFERING_FIELDS) & set(ok(client.get(f"{URL}/{paper['id']}", headers=h)))


def test_an_offering_without_a_department_serves_the_code_and_title_but_not_a_department(client, org, h, cycle):
    offering = uid()
    add_offering(org.id, offering, department_id=None)
    paper = make_papers(client, h, cycle["id"], offering, ["END"])[0]
    assert (paper["course_code"], paper["course_title"]) == ("CS101", "Programming")
    assert "department_id" not in paper


def test_another_organisations_offering_row_is_never_served(client, org, other_org, h, cycle):
    offering = uid()
    add_offering(other_org.id, offering, course_code="THEIRS", course_title="Not yours")
    paper = make_papers(client, h, cycle["id"], offering, ["END"])[0]
    assert not set(OFFERING_FIELDS) & set(paper)
    add_offering(org.id, offering, course_code="MINE", course_title="Mine")
    assert ok(client.get(f"{URL}/{paper['id']}", headers=h))["course_code"] == "MINE"


def test_a_mixed_page_serves_each_paper_its_own_offering_and_costs_one_offering_query(client, org, h, cycle):
    populated, partial, missing, no_department = uid(), uid(), uid(), uid()
    department = uid()
    add_offering(org.id, populated, course_code="POP", course_title="Populated", department_id=department)
    add_offering(org.id, partial, course_code=None, course_title=None, department_id=None, status="open")
    add_offering(org.id, no_department, course_code="NOD", course_title="No department", department_id=None)
    for offering in (populated, partial, missing, no_department):
        make_papers(client, h, cycle["id"], offering, ["END", "INT"])
    statements: list[str] = []

    def record(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    event.listen(engine, "before_cursor_execute", record)
    try:
        items = ok(client.get(f"{URL}?exam_cycle_id={cycle['id']}", headers=h))["items"]
    finally:
        event.remove(engine, "before_cursor_execute", record)
    assert len(items) == 8
    by_offering: dict[str, list[dict]] = {}
    for paper in items:
        by_offering.setdefault(paper["course_offering_id"], []).append(paper)
    assert {o: {tuple(sorted(offering_facts(p))) for p in ps} for o, ps in by_offering.items()} == {
        populated: {("course_code", "course_title", "department_id")},
        partial: {()},
        missing: {()},
        no_department: {("course_code", "course_title")},
    }
    assert {p["course_code"] for p in by_offering[populated]} == {"POP"}
    assert {p["department_id"] for p in by_offering[populated]} == {department}
    assert len([s for s in statements if "examinations_offering_ref" in s]) == 1  # one batched read, no N+1


def test_the_served_fields_match_the_contracts_optional_read_only_strings(client, org, h, cycle):
    schema = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))["components"]["schemas"]["ExamPaper"]
    for name in OFFERING_FIELDS:
        assert schema["properties"][name]["type"] == "string" and schema["properties"][name]["readOnly"] is True
        assert name not in schema["required"]  # so omitting it is valid, and null would not be
    assert schema["properties"]["department_id"]["format"] == "uuid"
    offering = uid()
    add_offering(org.id, offering)
    paper = make_papers(client, h, cycle["id"], offering, ["END"])[0]
    assert set(paper) <= set(schema["properties"]) and set(schema["required"]) <= set(paper)
    assert all(isinstance(paper[name], str) for name in OFFERING_FIELDS)


def test_the_department_filter_still_finds_papers_by_the_read_models_department(client, org, h, cycle):
    department, offering, other, partial = uid(), uid(), uid(), uid()
    add_offering(org.id, offering, department_id=department)
    add_offering(org.id, other, department_id=uid())
    add_offering(org.id, partial, course_code=None, course_title=None, department_id=None, status="open")
    mine = make_papers(client, h, cycle["id"], offering, ["END"])
    make_papers(client, h, cycle["id"], other, ["END"])
    make_papers(client, h, cycle["id"], partial, ["END"])
    found = ok(client.get(f"{URL}?department_id={department}", headers=h))
    assert [p["id"] for p in found["items"]] == [p["id"] for p in mine] and found["total"] == 1
    assert found["items"][0]["department_id"] == department
    assert ok(client.get(f"{URL}?department_id={uid()}", headers=h)) == {"items": [], "total": 0}
