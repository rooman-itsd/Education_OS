"""Decision D6 (issue #325): a faculty member lists and reads only the exam papers they hold a duty for (key
`paper:read-assigned`); `paper:read` widens it to every paper of the organisation. The papers carry no student or marks
data, but which papers exist is not every teacher's business."""

import pytest

pytest.importorskip("eos_core", reason="needs eos_core on PYTHONPATH (see conftest.py)")

from conftest import (  # noqa: E402
    BASE,
    FACULTY,
    HEAD,
    STUDENT,
    VIEWER,
    make_cycle,
    make_duty,
    make_grading,
    make_papers,
    make_session,
    ok,
    uid,
)

URL = f"{BASE}/papers"


@pytest.fixture
def world(client, org, h):
    """Four papers of four offerings: A and B for evaluation and moderation, C written in a session, D nobody's."""
    scheme = make_grading(client, h)
    ok(client.post(f"{BASE}/grading-schemes/{scheme['id']}/set-default", headers=h))
    cycle = make_cycle(client, h)
    a, b, c, d = (make_papers(client, h, cycle["id"], uid(), ["END"])[0] for _ in range(4))
    session = make_session(client, h, cycle["id"], [c["id"]])
    return {"cycle": cycle, "a": a, "b": b, "c": c, "d": d, "session": session}


def ids(response) -> set[str]:
    return {p["id"] for p in ok(response)["items"]}


def test_a_faculty_member_lists_only_the_papers_of_their_duties(client, org, h, world):
    me, mine = org.user(FACULTY)
    other, theirs = org.user(FACULTY)
    make_duty(client, h, me, "evaluation", paper_id=world["a"]["id"])
    make_duty(client, h, me, "moderation", paper_id=world["b"]["id"])
    make_duty(client, h, me, "invigilation", session_id=world["session"]["id"])  # the papers written in the session
    make_duty(client, h, other, "evaluation", paper_id=world["d"]["id"])

    assert ids(client.get(URL, headers=mine)) == {world["a"]["id"], world["b"]["id"], world["c"]["id"]}
    assert ids(client.get(URL, headers=theirs)) == {world["d"]["id"]}
    body = ok(client.get(URL, headers=mine))
    assert body["total"] == 3
    # The filters narrow the caller's own papers; they never widen them.
    assert ids(client.get(f"{URL}?exam_cycle_id={world['cycle']['id']}&status=draft", headers=theirs)) == {
        world["d"]["id"]
    }
    assert ids(client.get(f"{URL}?course_offering_id={world['d']['course_offering_id']}", headers=mine)) == set()


def test_a_faculty_member_reads_a_paper_of_their_duties_and_is_refused_any_other(client, org, h, world):
    me, mine = org.user(FACULTY)
    make_duty(client, h, me, "evaluation", paper_id=world["a"]["id"])
    assert ok(client.get(f"{URL}/{world['a']['id']}", headers=mine))["id"] == world["a"]["id"]
    detail = client.get(f"{URL}/{world['b']['id']}", headers=mine)
    assert detail.status_code == 403 and detail.json()["detail"]["code"] == "forbidden"
    assert client.get(f"{URL}/{uid()}", headers=mine).status_code == 404  # a paper that does not exist


def test_a_duty_that_is_cancelled_takes_the_paper_away(client, org, h, world):
    me, mine = org.user(FACULTY)
    duty = make_duty(client, h, me, "evaluation", paper_id=world["a"]["id"])
    assert ids(client.get(URL, headers=mine)) == {world["a"]["id"]}
    ok(client.post(f"{BASE}/duties/{duty['id']}/cancel", json={"reason": "reassigned"}, headers=h))
    assert ids(client.get(URL, headers=mine)) == set()
    assert client.get(f"{URL}/{world['a']['id']}", headers=mine).status_code == 403


def test_the_controller_the_head_and_the_viewer_keep_every_paper(client, org, h, world):
    everything = {world[k]["id"] for k in "abcd"}
    assert ids(client.get(URL, headers=h)) == everything
    for role in (HEAD, VIEWER):
        _, headers = org.user(role)
        assert ids(client.get(URL, headers=headers)) == everything, role
        assert ok(client.get(f"{URL}/{world['d']['id']}", headers=headers))["id"] == world["d"]["id"]


def test_the_papers_of_another_organisation_and_a_student_are_never_listed(client, org, other_org, h, world):
    me, mine = org.user(FACULTY)
    make_duty(client, h, me, "evaluation", paper_id=world["a"]["id"])
    # A faculty member of another organisation holds no duty here, so sees nothing; the paper itself is not found there.
    _, elsewhere = other_org.user(FACULTY)
    assert ids(client.get(URL, headers=elsewhere)) == set()
    assert client.get(f"{URL}/{world['a']['id']}", headers=other_org.controller()).status_code == 404
    _, student = org.user(STUDENT)
    assert client.get(URL, headers=student).status_code == 403
    assert client.get(URL).status_code == 401
