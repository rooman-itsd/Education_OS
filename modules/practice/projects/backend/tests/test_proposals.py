"""Proposals, coordinator-created projects, approval and rejection (docs/user-stories.md PR)."""

from conftest import PERIOD, audit, events
from eos_projects.infrastructure.models import new_id


def test_coordinator_creates_an_active_project(studio):
    s = studio
    p = s.project
    assert p["status"] == "active" and p["lead_id"] == s.lead_id and p["guide_ids"] == [s.guide_id]
    assert p["member_count"] == 2 and p["milestones_total"] == 0 and p["milestones_accepted"] == 0
    assert p["kind"] == "Capstone" and p["external_partner"] is None and p["outcome"] is None
    assert events("projects.project.approved", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": p["id"],
        "title": "Solar irrigation pump",
        "kind": "Capstone",
        "member_ids": [s.lead_id, s.member_id],
        "guide_ids": [s.guide_id],
        "starts_on": "2026-08-01",
        "ends_on": "2027-04-30",
    }
    assert (s.coordinator_id, "project.approved") in audit(p["id"])
    detail = s.get(f"/projects/{p['id']}", s.viewer).json()
    assert [(m["person_id"], m["role"]) for m in detail["members"]] == [(s.lead_id, "lead"), (s.member_id, "member")]
    assert [g["person_id"] for g in detail["guides"]] == [s.guide_id] and detail["milestones"] == []


def test_coordinator_create_needs_a_lead_and_a_guide_who_is_not_on_the_team(studio):
    s = studio
    a, b, g = new_id(), new_id(), new_id()
    base = {"title": "X", **PERIOD}
    cases = [
        ({"member_ids": [a, b], "guide_ids": [g]}, "no_lead"),
        ({"member_ids": [a], "lead_id": a, "guide_ids": []}, "guide_required"),
        ({"member_ids": [a, b], "lead_id": a, "guide_ids": [b]}, "member_is_guide"),
    ]
    for body, expected in cases:
        r = s.post("/projects", {**base, **body}, s.coordinator)
        assert r.status_code == 409 and r.json()["detail"]["code"] == expected, body
    # The lead is put on the team even when member_ids leaves them out.
    r = s.post("/projects", {**base, "member_ids": [b], "lead_id": a, "guide_ids": [g]}, s.coordinator)
    assert r.status_code == 201 and r.json()["member_count"] == 2 and r.json()["lead_id"] == a
    r = s.post("/projects", {**base, "starts_on": "2027-01-01", "ends_on": "2026-12-01"}, s.coordinator)
    assert r.status_code == 422


def test_learner_proposes_and_leads(studio):
    s = studio
    ignored = {"member_ids": [s.member_id], "lead_id": s.member_id, "guide_ids": [s.guide_id]}
    r = s.post("/projects", {"title": "Campus compost study", "kind": "Research", **PERIOD, **ignored}, s.outsider)
    assert r.status_code == 201
    p = r.json()
    assert p["status"] == "proposed" and p["lead_id"] == s.outsider_id and p["guide_ids"] == []
    assert p["member_count"] == 1
    assert events("projects.project.proposed", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": p["id"],
        "title": "Campus compost study",
        "kind": "Research",
        "lead_id": s.outsider_id,
    }
    assert (s.outsider_id, "project.proposed") in audit(p["id"])


def test_lead_edits_the_proposal_and_its_team_until_it_is_decided(studio):
    s = studio
    p = s.propose(s.outsider)
    r = s.patch(
        f"/projects/{p['id']}", {"summary": "Compost from the canteen", "external_partner": "Green Co"}, s.outsider
    )
    assert r.status_code == 200 and r.json()["summary"] == "Compost from the canteen"
    assert r.json()["title"] == "Campus compost study"  # fields left out keep their value
    assert s.patch(f"/projects/{p['id']}", {"ends_on": "2026-01-01"}, s.outsider).status_code == 422
    r = s.post(f"/projects/{p['id']}/members", {"person_id": s.member_id}, s.outsider)
    assert r.status_code == 201 and r.json()["role"] == "member"
    assert events("projects.member.added", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": p["id"],
        "person_id": s.member_id,
        "role": "member",
    }
    # A team member who is not the lead cannot change the proposal.
    r = s.patch(f"/projects/{p['id']}", {"title": "Mine now"}, s.member)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_lead"
    # After approval the lead no longer edits; the coordinator still can.
    s.post(f"/projects/{p['id']}/decision", {"decision": "approved", "guide_ids": [s.guide2_id]}, s.coordinator)
    r = s.patch(f"/projects/{p['id']}", {"title": "Late change"}, s.outsider)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "not_proposed"
    assert s.post(f"/projects/{p['id']}/members", {"person_id": new_id()}, s.outsider).status_code == 403
    assert s.patch(f"/projects/{p['id']}", {"title": "Compost 2"}, s.coordinator).json()["title"] == "Compost 2"


def test_a_learner_cannot_edit_someone_elses_proposal(studio):
    s = studio
    p = s.propose(s.outsider)
    assert s.patch(f"/projects/{p['id']}", {"title": "x"}, s.lead).status_code == 404
    assert s.post(f"/projects/{p['id']}/members", {"person_id": s.lead_id}, s.lead).status_code == 404
    assert s.delete(f"/projects/{p['id']}/members/{s.outsider_id}", s.lead).status_code == 404
    assert s.get(f"/projects/{p['id']}", s.lead).status_code == 404


def test_approve_needs_a_guide_and_publishes(studio):
    s = studio
    p = s.propose(s.outsider)
    path = f"/projects/{p['id']}/decision"
    r = s.post(path, {"decision": "approved"}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "guide_required"
    r = s.post(path, {"decision": "approved", "guide_ids": [s.outsider_id]}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "member_is_guide"
    r = s.post(path, {"decision": "approved", "guide_ids": [s.guide_id, s.guide2_id]}, s.coordinator)
    assert r.status_code == 200
    assert r.json()["status"] == "active" and r.json()["guide_ids"] == [s.guide_id, s.guide2_id]
    approved = events("projects.project.approved", s.org.id)[-1]
    assert approved["project_id"] == p["id"] and approved["member_ids"] == [s.outsider_id]
    assert approved["guide_ids"] == [s.guide_id, s.guide2_id]
    r = s.post(path, {"decision": "rejected", "reason": "Too late"}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"


def test_reject_needs_a_reason_and_closes_the_proposal(studio):
    s = studio
    p = s.propose(s.outsider)
    path = f"/projects/{p['id']}/decision"
    r = s.post(path, {"decision": "rejected"}, s.coordinator)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "reason_required"
    r = s.post(path, {"decision": "rejected", "reason": "Overlaps an existing project"}, s.coordinator)
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    assert r.json()["reason"] == "Overlaps an existing project"
    assert events("projects.project.rejected", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": p["id"],
        "reason": "Overlaps an existing project",
    }
    r = s.patch(f"/projects/{p['id']}", {"title": "x"}, s.outsider)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"
    assert s.patch(f"/projects/{p['id']}", {"title": "x"}, s.coordinator).status_code == 409


def test_list_projects_filters_and_pages(studio):
    s = studio
    second = s.new_project("Water quality survey", kind="Research", guide_ids=[s.guide2_id])
    s.propose(s.outsider)
    ids = lambda r: [p["id"] for p in r.json()["items"]]  # noqa: E731
    assert len(ids(s.get("/projects", s.viewer))) == 3
    assert ids(s.get("/projects?status=active&kind=Research", s.viewer)) == [second["id"]]
    assert ids(s.get(f"/projects?guide_id={s.guide2_id}", s.coordinator)) == [second["id"]]
    assert len(ids(s.get(f"/projects?member_id={s.lead_id}", s.coordinator))) == 2
    assert ids(s.get("/projects?q=WATER", s.coordinator)) == [second["id"]]
    assert ids(s.get("/projects?academic_year=2025-26", s.coordinator)) == []
    first = s.get("/projects?limit=2", s.viewer).json()
    assert len(first["items"]) == 2 and first["next_cursor"]
    rest = s.get(f"/projects?limit=2&cursor={first['next_cursor']}", s.viewer).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert s.get("/projects?status=open", s.viewer).status_code == 422
    assert s.get("/projects?guide_id=nobody", s.viewer).status_code == 422
    assert s.get("/projects?limit=101", s.viewer).status_code == 422
    assert s.get("/projects?cursor=garbage", s.viewer).status_code == 200  # an unreadable cursor starts over


def test_guide_sees_only_the_projects_they_guide(studio):
    s = studio
    other = s.new_project("Water quality survey", guide_ids=[s.guide2_id])
    r = s.get("/projects?status=active", s.guide)
    assert [p["id"] for p in r.json()["items"]] == [s.project["id"]]
    assert s.get(f"/projects/{s.project['id']}", s.guide).status_code == 200
    assert s.get(f"/projects/{other['id']}", s.guide).status_code == 404
    assert s.get(f"/projects/{other['id']}/milestones", s.guide).status_code == 404
