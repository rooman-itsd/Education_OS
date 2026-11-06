"""Final submission and evaluation (docs/user-stories.md FE)."""

from conftest import audit, events


def test_final_submission_warns_about_milestones_not_accepted(studio):
    s = studio
    done = s.milestone("Design review")
    s.submit(done["id"])
    s.post(f"/milestones/{done['id']}/review", {"decision": "accepted"}, s.guide)
    open_one = s.milestone("Field trial", "2027-02-01")
    dropped = s.milestone("Poster")
    s.patch(f"/milestones/{dropped['id']}", {"status": "cancelled"}, s.guide)
    r = s.post(f"/projects/{s.project['id']}/submit", {"note": "Final report attached"}, s.lead)
    assert r.status_code == 201
    body = r.json()
    assert body["project"]["status"] == "submitted" and body["milestones_not_accepted"] == [open_one["id"]]
    assert body["submission"]["milestone_id"] is None and body["submission"]["version"] == 1
    assert events("projects.project.submitted", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": s.project["id"],
        "submission_id": body["submission"]["id"],
        "submitted_by": s.lead_id,
    }
    r = s.post(f"/projects/{s.project['id']}/submit", {"note": "Again"}, s.lead)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "project_not_active"
    r = s.post(f"/projects/{s.project['id']}/submit", {"note": "x"}, s.outsider)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_member"


def test_guide_returns_then_completes_the_project(studio):
    s = studio
    pid = s.project["id"]
    r = s.post(f"/projects/{pid}/evaluation", {"decision": "completed", "outcome": "Distinction"}, s.guide)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "project_not_submitted"
    s.post(f"/projects/{pid}/submit", {"note": "v1"}, s.member)
    r = s.post(f"/projects/{pid}/evaluation", {"decision": "returned", "comments": "Add results"}, s.guide2)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_guide"
    r = s.post(f"/projects/{pid}/evaluation", {"decision": "returned", "comments": "Add results"}, s.guide)
    assert r.status_code == 200 and r.json()["status"] == "active"
    assert events("projects.project.returned", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": pid,
        "reviewer_id": s.guide_id,
    }
    second = s.post(f"/projects/{pid}/submit", {"note": "v2"}, s.member).json()["submission"]
    assert second["version"] == 2
    r = s.post(f"/projects/{pid}/evaluation", {"decision": "completed"}, s.guide)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "outcome_required"
    body = {"decision": "completed", "outcome": "Distinction", "score": 91, "comments": "Excellent"}
    r = s.post(f"/projects/{pid}/evaluation", body, s.guide)
    assert r.status_code == 200
    p = r.json()
    assert p["status"] == "completed" and p["outcome"] == "Distinction" and p["score"] == 91
    assert events("projects.project.completed", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": pid,
        "title": "Solar irrigation pump",
        "kind": "Capstone",
        "member_ids": [s.lead_id, s.member_id],
        "guide_ids": [s.guide_id],
        "outcome": "Distinction",
        "score": 91,
    }
    assert [a for _, a in audit(pid) if a.startswith("project.")][-4:] == [
        "project.submitted",
        "project.returned",
        "project.submitted",
        "project.completed",
    ]
    # A completed project changes no more.
    assert s.patch(f"/projects/{pid}", {"title": "x"}, s.coordinator).status_code == 409
    assert s.post(f"/projects/{pid}/cancel", {"reason": "Too late"}, s.coordinator).status_code == 409
    assert s.post(f"/projects/{pid}/evaluation", body, s.guide).status_code == 409
