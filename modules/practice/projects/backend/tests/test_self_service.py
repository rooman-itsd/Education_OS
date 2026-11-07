"""The caller's own projects, milestones due and work to review: the endpoints behind the widgets
(docs/user-stories.md SS and WG)."""

from datetime import UTC, datetime

from eos_projects.application import service


def test_my_projects_in_progress_first_with_progress_and_next_milestone(studio):
    s = studio
    m1 = s.milestone("Design review", "2026-11-10")
    s.milestone("Field trial", "2027-02-01")
    s.submit(m1["id"])
    s.post(f"/milestones/{m1['id']}/review", {"decision": "accepted"}, s.guide)
    proposal = s.propose(s.lead, "Compost study")
    finished = s.new_project("Old project")
    s.post(f"/projects/{finished['id']}/submit", {"note": "done"}, s.lead)
    s.post(f"/projects/{finished['id']}/evaluation", {"decision": "completed", "outcome": "Pass"}, s.guide)
    rows = s.get("/me/projects", s.lead).json()
    assert [p["id"] for p in rows] == [s.project["id"], proposal["id"]]
    first = rows[0]
    assert first["my_role"] == "lead" and first["milestones_accepted"] == 1 and first["milestones_total"] == 2
    assert first["next_milestone"]["title"] == "Field trial"
    assert rows[1]["status"] == "proposed" and rows[1]["next_milestone"] is None
    past = s.get("/me/projects?include_past=true", s.lead).json()
    assert [p["id"] for p in past] == [s.project["id"], proposal["id"], finished["id"]]
    assert [p["my_role"] for p in s.get("/me/projects", s.member).json()] == ["member"]
    assert s.get("/me/projects", s.outsider).json() == []


def test_my_milestones_due_within_the_window_with_overdue_first(studio):
    s = studio
    overdue = s.milestone("Overdue log", "2026-11-01")
    soon = s.milestone("Design review", "2026-11-10")
    later = s.milestone("Field trial", "2027-02-01")
    submitted = s.milestone("Survey", "2026-11-05")
    s.submit(submitted["id"])
    rows = s.get("/me/milestones", s.member).json()
    assert [m["id"] for m in rows] == [overdue["id"], soon["id"]]
    assert rows[0]["overdue"] is True and rows[0]["days_left"] == -3
    assert rows[1]["overdue"] is False and rows[1]["days_left"] == 6
    assert rows[0]["project_title"] == "Solar irrigation pump"
    assert [m["id"] for m in s.get("/me/milestones?within_days=180", s.lead).json()] == [
        overdue["id"],
        soon["id"],
        later["id"],
    ]
    assert s.get("/me/milestones?within_days=0", s.lead).status_code == 422
    assert s.get("/me/milestones?within_days=181", s.lead).status_code == 422
    assert s.get("/me/milestones", s.outsider).json() == []
    # A returned milestone is the team's again.
    s.post(f"/milestones/{submitted['id']}/review", {"decision": "returned", "comments": "Redo"}, s.guide)
    assert submitted["id"] in [m["id"] for m in s.get("/me/milestones", s.member).json()]


def test_due_dates_follow_asia_kolkata(studio, monkeypatch):
    s = studio
    s.milestone("Due on the 4th", "2026-11-04")
    # 18:45 UTC on 4 November is already 5 November in India: the milestone is overdue there.
    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 11, 4, 18, 45, tzinfo=UTC))
    row = s.get("/me/milestones", s.member).json()[0]
    assert row["overdue"] is True and row["days_left"] == -1


def test_my_reviews_oldest_first_for_the_guide_only(studio):
    s = studio
    m = s.milestone("Design review")
    s.submit(m["id"])
    other = s.new_project("Water survey", member_ids=[s.outsider_id], lead_id=s.outsider_id)
    s.post(f"/projects/{other['id']}/submit", {"note": "Final"}, s.outsider)
    rows = s.get("/me/reviews", s.guide).json()
    assert [(r["kind"], r["project_id"]) for r in rows] == [("milestone", s.project["id"]), ("final", other["id"])]
    assert rows[0]["milestone_id"] == m["id"] and rows[0]["milestone_title"] == "Design review"
    assert rows[0]["submission"]["version"] == 1 and rows[0]["waiting_days"] == 0
    assert rows[1]["milestone_id"] is None and rows[1]["milestone_title"] is None
    assert rows[1]["project_title"] == "Water survey"
    assert len(s.get("/me/reviews?limit=1", s.guide).json()) == 1
    assert s.get("/me/reviews", s.guide2).json() == []
    s.post(f"/milestones/{m['id']}/review", {"decision": "accepted"}, s.guide)
    assert [r["kind"] for r in s.get("/me/reviews", s.guide).json()] == ["final"]


def test_waiting_days_count_business_days_since_submission(studio, monkeypatch):
    s = studio
    m = s.milestone()
    s.submit(m["id"])
    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 11, 7, 6, 0, tzinfo=UTC))
    assert s.get("/me/reviews", s.guide).json()[0]["waiting_days"] == 3


def test_active_projects_for_the_guide_and_the_coordinator(studio):
    """projects.active: GET /projects?status=active. A guide sees what they guide, a coordinator everything."""
    s = studio
    s.new_project("Water survey", guide_ids=[s.guide2_id])
    s.propose(s.outsider)
    guide_view = s.get("/projects?status=active", s.guide).json()["items"]
    assert [p["id"] for p in guide_view] == [s.project["id"]]
    assert len(s.get("/projects?status=active", s.coordinator).json()["items"]) == 2
