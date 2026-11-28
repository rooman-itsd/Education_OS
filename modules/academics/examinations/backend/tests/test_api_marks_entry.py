"""openMarksEntry (decision D3, issue #325): a controller moves a scheduled paper into `marks_entry`. Explicit, audited,
safe to repeat, and only forward from `scheduled`. A paper is put in `scheduled` with `set_row`: scheduling a session does
that through its own operation, covered in test_api_sessions.py."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    STUDENT,
    VIEWER,
    audit_entries,
    err,
    make_cycle,
    make_grading,
    make_papers,
    ok,
    session_for,
    set_row,
)
from eos_examinations.infrastructure.models import ExamCycleRow, ExamPaperRow  # noqa: E402

URL = f"{BASE}/papers"


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


@pytest.fixture
def scheduled(client, org, h, cycle) -> dict:
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    set_row(org.id, ExamPaperRow, paper["id"], status="scheduled")
    return paper


def open_entry(client, headers, paper_id):
    return client.post(f"{URL}/{paper_id}/marks-entry", headers=headers)


def status_of(org, paper_id: str) -> str:
    with session_for(org.id) as db:
        return db.get(ExamPaperRow, paper_id).status


def opened_audits(org, paper_id: str) -> list:
    return [a for a in audit_entries(org.id, paper_id) if a.action == "exam_paper.marks_entry_opened"]


def test_a_controller_opens_a_scheduled_paper_and_it_is_audited(client, org, h, scheduled):
    body = ok(open_entry(client, h, scheduled["id"]))
    assert body["id"] == scheduled["id"] and body["status"] == "marks_entry"
    assert status_of(org, scheduled["id"]) == "marks_entry"
    (entry,) = opened_audits(org, scheduled["id"])
    assert (entry.before, entry.after) == ({"status": "scheduled"}, {"status": "marks_entry"})
    # The paper now takes marks: listMarks answers for it (no candidate exists yet, so the list is empty).
    listing = ok(client.get(f"{URL}/{scheduled['id']}/marks", headers=h))
    assert (listing["paper_status"], listing["items"]) == ("marks_entry", [])


def test_a_repeated_request_changes_and_audits_nothing(client, org, h, scheduled):
    first = ok(open_entry(client, h, scheduled["id"]))
    second = ok(open_entry(client, h, scheduled["id"]))
    assert first == second
    assert len(opened_audits(org, scheduled["id"])) == 1


@pytest.mark.parametrize("state", ["draft", "moderation", "locked"])
def test_only_a_scheduled_paper_can_be_opened(client, org, h, cycle, state):
    paper = make_papers(client, h, cycle["id"], None, ["END"])[0]
    set_row(org.id, ExamPaperRow, paper["id"], status=state)
    detail = err(open_entry(client, h, paper["id"]), 409, "invalid_status_transition")
    assert detail["details"]["from"] == state and detail["details"]["to"] == "marks_entry"
    assert status_of(org, paper["id"]) == state
    assert opened_audits(org, paper["id"]) == []


@pytest.mark.parametrize("cycle_status", ["results_published", "closed"])
def test_a_paper_of_a_cycle_with_published_results_stays_where_it_is(client, org, h, scheduled, cycle_status):
    set_row(org.id, ExamCycleRow, scheduled["exam_cycle_id"], status=cycle_status)
    err(open_entry(client, h, scheduled["id"]), 409, "cycle_results_published")
    assert status_of(org, scheduled["id"]) == "scheduled"


def test_only_a_caller_who_manages_papers_can_open_one(client, org, other_org, h, scheduled):
    for role in (FACULTY, STUDENT, VIEWER):
        _, headers = org.user(role)
        assert open_entry(client, headers, scheduled["id"]).status_code == 403, role
    assert client.post(f"{URL}/{scheduled['id']}/marks-entry").status_code == 401
    # Another organisation's controller does not find it.
    assert open_entry(client, other_org.controller(), scheduled["id"]).status_code == 404
    assert status_of(org, scheduled["id"]) == "scheduled"


def test_an_unknown_paper_is_404(client, h):
    err(open_entry(client, h, "00000000-0000-4000-8000-000000000001"), 404, "exam_paper_not_found")
