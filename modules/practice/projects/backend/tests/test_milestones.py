"""Milestones, submissions and reviews (docs/user-stories.md MS and SR)."""

from conftest import audit, events


def test_guide_adds_milestones_in_due_order(studio):
    s = studio
    late = s.milestone("Final report", "2027-03-31")
    early = s.milestone("Design review", "2026-11-10")
    assert early["status"] == "pending" and early["weight"] == 20 and early["overdue"] is False
    assert early["latest_submission_at"] is None and early["project_id"] == s.project["id"]
    assert events("projects.milestone.created", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "milestone_id": early["id"],
        "project_id": s.project["id"],
        "due_on": "2026-11-10",
    }
    for headers in (s.guide, s.coordinator, s.viewer, s.lead):
        r = s.get(f"/projects/{s.project['id']}/milestones", headers)
        assert [m["id"] for m in r.json()] == [early["id"], late["id"]]
    assert s.get(f"/projects/{s.project['id']}", s.member).json()["milestones_total"] == 2
    # The coordinator may add milestones too; a guide of another project may not.
    body = {"title": "Prototype", "due_on": "2027-01-15"}
    assert s.post(f"/projects/{s.project['id']}/milestones", body, s.coordinator).status_code == 201
    r = s.post(f"/projects/{s.project['id']}/milestones", body, s.guide2)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_guide"
    for bad in (
        {"title": "x"},
        {"title": "x", "due_on": "2027-01-01", "weight": 101},
        {"title": "", "due_on": "2027-01-01"},
    ):
        assert s.post(f"/projects/{s.project['id']}/milestones", bad, s.guide).status_code == 422, bad


def test_milestones_only_on_active_projects(studio):
    s = studio
    p = s.propose(s.outsider)
    r = s.post(f"/projects/{p['id']}/milestones", {"title": "x", "due_on": "2027-01-01"}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "project_not_active"


def test_move_and_cancel_a_milestone_until_it_is_accepted(studio):
    s = studio
    m = s.milestone()
    r = s.patch(f"/milestones/{m['id']}", {"due_on": "2026-11-20", "description": "Slides and model"}, s.guide)
    assert r.status_code == 200 and r.json()["due_on"] == "2026-11-20" and r.json()["title"] == "Design review"
    assert r.json()["description"] == "Slides and model"
    assert s.patch(f"/milestones/{m['id']}", {"title": None}, s.guide).status_code == 422
    assert s.patch(f"/milestones/{m['id']}", {"weight": -1}, s.guide).status_code == 422
    assert s.patch(f"/milestones/{m['id']}", {"title": "x"}, s.guide2).status_code == 403
    other = s.milestone("Survey")
    r = s.patch(f"/milestones/{other['id']}", {"status": "cancelled", "reason": "Merged"}, s.guide)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    r = s.patch(f"/milestones/{other['id']}", {"title": "Back"}, s.guide)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"
    assert (s.guide_id, "milestone.cancelled") in audit(other["id"])
    detail = s.get(f"/projects/{s.project['id']}", s.guide).json()
    assert detail["milestones_total"] == 1  # a cancelled milestone does not count
    s.submit(m["id"])
    s.post(f"/milestones/{m['id']}/review", {"decision": "accepted"}, s.guide)
    r = s.patch(f"/milestones/{m['id']}", {"due_on": "2026-12-01"}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "milestone_accepted"
    r = s.patch(f"/milestones/{m['id']}", {"status": "cancelled"}, s.guide)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "milestone_accepted"


def test_member_submits_and_guide_returns_then_accepts(studio):
    s = studio
    m = s.milestone()
    doc = "6f1c2a5e-0b8e-4d3a-9c7d-2b1e0f4a5c6d"
    r = s.post(f"/milestones/{m['id']}/submissions", {"note": "First draft", "document_ids": [doc]}, s.member)
    assert r.status_code == 201
    first = r.json()
    assert first["version"] == 1 and first["submitted_by"] == s.member_id and first["document_ids"] == [doc]
    assert first["milestone_id"] == m["id"] and first["review"] is None
    assert events("projects.milestone.submitted", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "milestone_id": m["id"],
        "project_id": s.project["id"],
        "submission_id": first["id"],
        "version": 1,
        "submitted_by": s.member_id,
    }
    r = s.submit(m["id"], s.lead)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"  # already submitted
    path = f"/milestones/{m['id']}/review"
    r = s.post(path, {"decision": "returned"}, s.guide)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "comments_required"
    r = s.post(path, {"decision": "returned", "comments": "Add the cost estimate"}, s.guide)
    assert r.status_code == 200 and r.json()["status"] == "returned"
    assert events("projects.milestone.returned", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "milestone_id": m["id"],
        "project_id": s.project["id"],
        "reviewer_id": s.guide_id,
    }
    r = s.post(path, {"decision": "accepted"}, s.guide)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "nothing_submitted"
    second = s.submit(m["id"], s.lead, note="With costs").json()
    assert second["version"] == 2
    r = s.post(path, {"decision": "accepted", "score": 85.5, "comments": "Good"}, s.guide)
    assert r.status_code == 200 and r.json()["status"] == "accepted" and r.json()["latest_submission_at"]
    assert events("projects.milestone.accepted", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "milestone_id": m["id"],
        "project_id": s.project["id"],
        "reviewer_id": s.guide_id,
        "score": 85.5,
    }
    history = s.get(f"/milestones/{m['id']}/submissions", s.member).json()
    assert [h["version"] for h in history] == [1, 2]
    assert history[0]["review"]["decision"] == "returned"
    assert history[0]["review"]["comments"] == "Add the cost estimate"
    assert history[1]["review"] == {
        "decision": "accepted",
        "comments": "Good",
        "score": 85.5,
        "reviewer_id": s.guide_id,
        "reviewed_at": history[1]["review"]["reviewed_at"],
    }
    assert s.get(f"/projects/{s.project['id']}", s.lead).json()["milestones_accepted"] == 1
    actions = [a for _, a in audit(m["id"])]
    assert actions.count("milestone.submitted") == 2 and "milestone.accepted" in actions
    # Submission notes and review comments never go into an event.
    for name in ("submitted", "accepted", "returned"):
        for payload in events(f"projects.milestone.{name}", s.org.id):
            assert "note" not in payload and "comments" not in payload


def test_only_members_submit_and_only_guides_review(studio):
    s = studio
    m = s.milestone()
    r = s.submit(m["id"], s.outsider)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_member"
    s.submit(m["id"])
    r = s.post(f"/milestones/{m['id']}/review", {"decision": "accepted"}, s.guide2)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_guide"
    # A coordinator manages but does not review.
    assert s.post(f"/milestones/{m['id']}/review", {"decision": "accepted"}, s.coordinator).status_code == 403
    for body in ({"note": ""}, {"note": "x" * 4001}, {"note": "x", "document_ids": ["file-1"]}, {}):
        assert s.post(f"/milestones/{m['id']}/submissions", body, s.member).status_code == 422, body
    assert s.post(f"/milestones/{m['id']}/review", {"decision": "accepted", "score": 101}, s.guide).status_code == 422
    assert s.post(f"/milestones/{m['id']}/review", {"decision": "maybe"}, s.guide).status_code == 422
    assert s.get(f"/milestones/{m['id']}/submissions", s.outsider).status_code == 404
    assert s.get(f"/milestones/{m['id']}/submissions", s.guide2).status_code == 404


def test_no_submission_on_a_cancelled_milestone_or_inactive_project(studio):
    s = studio
    m = s.milestone()
    s.patch(f"/milestones/{m['id']}", {"status": "cancelled"}, s.guide)
    assert s.submit(m["id"]).status_code == 409
    live = s.milestone("Live")
    s.post(f"/projects/{s.project['id']}/cancel", {"reason": "Stopped"}, s.coordinator)
    r = s.submit(live["id"])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "project_not_active"
