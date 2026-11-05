"""Edge inputs answer 422, 404 or 409, never a 500: numbers and dates past the columns, cursors we never handed out,
wildcards in searches, NUL characters, and a duplicate write that slips past the checks."""

import base64

from conftest import PERIOD
from eos_projects.infrastructure import repository

NUL = "\x00"


def test_numbers_past_the_bounds_are_refused(studio):
    s = studio
    huge = 2**63
    for path in (f"/me/milestones?within_days={huge}", f"/me/reviews?limit={huge}", f"/projects?limit={huge}"):
        assert s.get(path, s.lead if "milestones" in path else s.guide).status_code == 422, path
    body = {"title": "x", "due_on": "2027-01-01", "weight": 1e308}
    assert s.post(f"/projects/{s.project['id']}/milestones", body, s.guide).status_code == 422
    m = s.milestone()
    s.submit(m["id"])
    for score in (huge, -1, 100.5):
        r = s.post(f"/milestones/{m['id']}/review", {"decision": "accepted", "score": score}, s.guide)
        assert r.status_code == 422, score


def test_dates_at_the_ends_of_the_calendar_are_refused(studio):
    s = studio
    for over in ({"starts_on": "0001-01-01"}, {"ends_on": "9999-12-31"}):
        assert s.post("/projects", {"title": "x", **PERIOD, **over}, s.outsider).status_code == 422, over
    path = f"/projects/{s.project['id']}/milestones"
    assert s.post(path, {"title": "x", "due_on": "9999-12-31"}, s.guide).status_code == 422
    assert s.post(path, {"title": "x", "due_on": "9998-12-31"}, s.guide).status_code == 201
    assert s.get("/me/milestones?within_days=180", s.member).status_code == 200


def test_a_cursor_we_never_handed_out_starts_from_the_top(studio):
    s = studio
    s.new_project("Second")
    first = s.get("/projects?limit=1", s.viewer).json()
    for raw in (b"1000001", b"9223372036854775808", b"99999999999999999999", b"-5", b"x"):
        cursor = base64.urlsafe_b64encode(raw).decode()
        r = s.get(f"/projects?limit=1&cursor={cursor}", s.viewer)
        assert r.status_code == 200, r.text
        assert r.json() == first


def test_title_search_takes_wildcards_literally(studio):
    s = studio
    assert s.get("/projects?q=%25", s.viewer).json()["items"] == []
    assert s.get("/projects?q=_", s.viewer).json()["items"] == []
    s.new_project("Lab 5_A")
    assert [p["title"] for p in s.get("/projects?q=5_", s.viewer).json()["items"]] == ["Lab 5_A"]


def test_nul_characters_are_refused(studio):
    s = studio
    pid = s.project["id"]
    # The client sends a NUL percent-encoded; the server sees the character itself.
    assert s.get(f"/projects/{pid}%00", s.viewer).status_code == 404
    assert s.get("/milestones/%00/submissions", s.viewer).status_code == 404
    r = s.get("/projects?q=a%00b", s.viewer)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_query"
    assert s.get("/projects?kind=%00", s.viewer).status_code == 422
    assert s.patch(f"/projects/{pid}", {"title": f"a{NUL}"}, s.coordinator).status_code == 422
    assert s.post(f"/projects/{pid}/cancel", {"reason": f"Stop{NUL}now"}, s.coordinator).status_code == 422
    m = s.milestone()
    assert s.post(f"/milestones/{m['id']}/submissions", {"note": f"x{NUL}"}, s.member).status_code == 422
    assert s.get(f"/projects/{pid}", s.viewer).json()["status"] == "active"


def test_a_duplicate_submission_that_slips_past_the_lock_is_a_conflict(studio, monkeypatch):
    """Two submissions at once both count the same versions; the unique constraint catches the second one."""
    s = studio
    m = s.milestone()
    s.submit(m["id"])
    s.post(f"/milestones/{m['id']}/review", {"decision": "returned", "comments": "Redo"}, s.guide)
    real = repository.submissions
    monkeypatch.setattr(repository, "submissions", lambda db, project_id, milestone_id: [])
    r = s.submit(m["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_submitted"
    monkeypatch.setattr(repository, "submissions", real)
    # Nothing was half written, and the milestone can still be submitted.
    assert s.get(f"/projects/{s.project['id']}/milestones", s.member).json()[0]["status"] == "returned"
    assert s.submit(m["id"]).json()["version"] == 2
