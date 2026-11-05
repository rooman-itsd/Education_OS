"""The daily job: projects.milestone.overdue once per milestone (docs/user-stories.md JB)."""

from datetime import date

from conftest import audit, events
from eos_core.db import SessionLocal
from eos_projects.application import jobs


def test_overdue_is_published_once_the_day_after_the_due_date(studio):
    s = studio
    m = s.milestone("Design review", "2026-11-10")
    with SessionLocal() as db:
        jobs.flag_overdue_milestones(db, date(2026, 11, 10))
    assert events("projects.milestone.overdue", s.org.id) == []  # due today is not overdue yet
    with SessionLocal() as db:
        assert jobs.flag_overdue_milestones(db, date(2026, 11, 11)) >= 1
    assert events("projects.milestone.overdue", s.org.id) == [
        {"organisation_id": s.org.id, "milestone_id": m["id"], "project_id": s.project["id"], "due_on": "2026-11-10"}
    ]
    assert (None, "milestone.overdue") in audit(m["id"])
    with SessionLocal() as db:
        jobs.flag_overdue_milestones(db, date(2026, 11, 12))
    assert len(events("projects.milestone.overdue", s.org.id)) == 1


def test_submitted_accepted_cancelled_and_inactive_are_not_overdue(studio):
    s = studio
    submitted = s.milestone("Submitted", "2026-11-05")
    s.submit(submitted["id"])
    cancelled = s.milestone("Cancelled", "2026-11-05")
    s.patch(f"/milestones/{cancelled['id']}", {"status": "cancelled"}, s.guide)
    returned = s.milestone("Returned", "2026-11-05")
    s.submit(returned["id"])
    s.post(f"/milestones/{returned['id']}/review", {"decision": "returned", "comments": "Redo"}, s.guide)
    other = s.new_project("Stopped project")
    stopped = s.milestone("Stopped", "2026-11-05", project_id=other["id"])
    s.post(f"/projects/{other['id']}/cancel", {"reason": "Stopped"}, s.coordinator)
    with SessionLocal() as db:
        jobs.flag_overdue_milestones(db, date(2026, 11, 20))
    flagged = [e["milestone_id"] for e in events("projects.milestone.overdue", s.org.id)]
    assert flagged == [returned["id"]]
    assert stopped["id"] not in flagged


def test_run_daily_reports_counts(studio):
    with SessionLocal() as db:
        assert set(jobs.run_daily(db)) == {"milestones_overdue"}
