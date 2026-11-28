"""getMyExamSchedule (`GET /me/exam-schedule`, widget examinations.upcoming-assessments): the scheduled, not yet ended
sessions of the papers the caller is a candidate for, by start time. The clock is frozen at 2026-11-05 (conftest.py);
candidates are written through the model, since nothing creates them yet (registration is a later slice)."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    HEAD,
    STUDENT,
    err,
    make_cycle,
    make_grading,
    make_papers,
    make_session,
    ok,
    session_for,
    set_row,
    uid,
)
from eos_examinations.infrastructure.models import CandidateRow, ExamSessionRow  # noqa: E402

URL = f"{BASE}/me/exam-schedule"


@pytest.fixture
def cycle(client, h) -> dict:
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    return make_cycle(client, h)


def candidate(org, paper: dict, student_id: str, status: str = "eligible") -> None:
    with session_for(org.id) as db:
        db.add(
            CandidateRow(
                organisation_id=org.id,
                exam_cycle_id=paper["exam_cycle_id"],
                exam_paper_id=paper["id"],
                course_offering_id=paper["course_offering_id"],
                student_id=student_id,
                eligibility_status=status,
                eligibility_reasons=[],
            )
        )
        db.commit()


def schedule(client, headers, query: str = "") -> list[dict]:
    return ok(client.get(f"{URL}{query}", headers=headers))["items"]


def test_a_student_sees_the_sessions_of_the_papers_they_sit_by_start_time(client, org, h, cycle):
    student, mine = org.user(STUDENT)
    later, sooner, theirs = (make_papers(client, h, cycle["id"], uid(), ["END"])[0] for _ in range(3))
    s_later = make_session(
        client,
        h,
        cycle["id"],
        [later["id"]],
        starts_at="2026-11-27T09:00:00+00:00",
        ends_at="2026-11-27T12:00:00+00:00",
    )
    s_sooner = make_session(client, h, cycle["id"], [sooner["id"]], venue_label="Hall B")
    make_session(client, h, cycle["id"], [theirs["id"]])  # a paper this student does not sit
    candidate(org, later, student)
    candidate(org, sooner, student, "pending")

    items = schedule(client, mine)
    assert [i["exam_session_id"] for i in items] == [s_sooner["id"], s_later["id"]]
    first = items[0]
    assert first["exam_cycle_id"] == cycle["id"] and first["exam_paper_id"] == sooner["id"]
    assert first["course_offering_id"] == sooner["course_offering_id"] and first["component_code"] == "END"
    assert (first["starts_at"][:16], first["ends_at"][:16], first["venue_label"]) == (
        "2026-11-25T09:00",
        "2026-11-25T12:00",
        "Hall B",
    )
    assert (first["eligibility_status"], first["hall_ticket_status"]) == ("pending", None)
    assert items[1]["eligibility_status"] == "eligible"
    assert "course_code" not in first  # the offering's code arrives with its event; none was delivered here


def test_a_student_with_no_candidacy_has_an_empty_schedule_and_never_sees_anothers(client, org, other_org, h, cycle):
    paper = make_papers(client, h, cycle["id"], uid(), ["END"])[0]
    make_session(client, h, cycle["id"], [paper["id"]])
    student, mine = org.user(STUDENT)
    candidate(org, paper, student)
    _, other = org.user(STUDENT)
    assert schedule(client, other) == []
    _, elsewhere = other_org.user(STUDENT, user_id=student)  # the same user id in another organisation
    assert schedule(client, elsewhere) == []
    assert len(schedule(client, mine)) == 1


def test_cancelled_and_ended_sessions_and_the_date_filter(client, org, h, cycle):
    student, mine = org.user(STUDENT)
    papers = [make_papers(client, h, cycle["id"], uid(), ["END"])[0] for _ in range(3)]
    live = make_session(client, h, cycle["id"], [papers[0]["id"]])
    cancelled = make_session(client, h, cycle["id"], [papers[1]["id"]])
    ended = make_session(client, h, cycle["id"], [papers[2]["id"]])
    ok(client.post(f"{BASE}/sessions/{cancelled['id']}/cancel", json={"reason": "flood"}, headers=h))
    set_row(org.id, ExamSessionRow, ended["id"], starts_at=_dt("2026-11-02T09:00"), ends_at=_dt("2026-11-02T12:00"))
    for paper in papers:
        candidate(org, paper, student)
    assert [i["exam_session_id"] for i in schedule(client, mine)] == [live["id"]]  # today is 2026-11-05
    assert {i["exam_session_id"] for i in schedule(client, mine, "?date_from=2026-11-01")} == {live["id"], ended["id"]}
    assert schedule(client, mine, "?date_from=2026-11-26") == []  # the live session ended on the 25th
    err(client.get(f"{URL}?date_from=tomorrow", headers=mine), 400, "invalid_date")


def _dt(value: str):
    from datetime import UTC, datetime

    return datetime.fromisoformat(value).replace(tzinfo=UTC)


def test_only_a_student_reads_their_schedule(client, org, h):
    assert client.get(URL).status_code == 401
    for role in (FACULTY, HEAD):
        _, headers = org.user(role)
        assert client.get(URL, headers=headers).status_code == 403, role
