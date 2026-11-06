"""Teams, leads, guides and cancellation (docs/user-stories.md TM and CA)."""

from conftest import audit, events
from eos_projects.infrastructure.models import new_id


def test_coordinator_adds_and_removes_members_of_an_active_project(studio):
    s = studio
    pid = s.project["id"]
    r = s.post(f"/projects/{pid}/members", {"person_id": s.outsider_id}, s.coordinator)
    assert r.status_code == 201 and r.json()["person_id"] == s.outsider_id and r.json()["left_at"] is None
    r = s.post(f"/projects/{pid}/members", {"person_id": s.outsider_id}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_member"
    r = s.post(f"/projects/{pid}/members", {"person_id": s.guide_id}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "member_is_guide"
    assert s.delete(f"/projects/{pid}/members/{s.outsider_id}", s.coordinator).status_code == 204
    assert events("projects.member.removed", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": pid,
        "person_id": s.outsider_id,
    }
    assert s.delete(f"/projects/{pid}/members/{s.outsider_id}", s.coordinator).status_code == 404
    detail = s.get(f"/projects/{pid}", s.coordinator).json()
    gone = [m for m in detail["members"] if m["person_id"] == s.outsider_id]
    assert len(gone) == 1 and gone[0]["left_at"] is not None  # the record is kept
    assert detail["member_count"] == 2
    # A person who left may rejoin.
    assert s.post(f"/projects/{pid}/members", {"person_id": s.outsider_id}, s.coordinator).status_code == 201
    assert (s.coordinator_id, "member.removed") in audit(pid)


def test_the_lead_is_removed_only_after_another_member_is_made_lead(studio):
    s = studio
    pid = s.project["id"]
    r = s.delete(f"/projects/{pid}/members/{s.lead_id}", s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "member_is_lead"
    r = s.post(f"/projects/{pid}/members", {"person_id": s.member_id, "role": "lead"}, s.coordinator)
    assert r.status_code == 201 and r.json()["role"] == "lead"
    assert events("projects.member.added", s.org.id)[-1]["role"] == "lead"
    detail = s.get(f"/projects/{pid}", s.coordinator).json()
    assert detail["lead_id"] == s.member_id
    assert {m["person_id"]: m["role"] for m in detail["members"]}[s.lead_id] == "member"  # demoted
    assert s.delete(f"/projects/{pid}/members/{s.lead_id}", s.coordinator).status_code == 204
    # A new person may join directly as lead; there is still exactly one lead.
    newcomer = new_id()
    s.post(f"/projects/{pid}/members", {"person_id": newcomer, "role": "lead"}, s.coordinator)
    leads = [m for m in s.get(f"/projects/{pid}", s.coordinator).json()["members"] if m["role"] == "lead"]
    assert [m["person_id"] for m in leads] == [newcomer]


def test_replace_guides(studio):
    s = studio
    pid = s.project["id"]
    r = s.put(f"/projects/{pid}/guides", {"guide_ids": [s.guide2_id, s.guide_id]}, s.coordinator)
    assert r.status_code == 200 and r.json()["guide_ids"] == [s.guide_id, s.guide2_id]
    assert events("projects.guide.assigned", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": pid,
        "guide_ids": [s.guide2_id, s.guide_id],
    }
    r = s.put(f"/projects/{pid}/guides", {"guide_ids": [s.guide2_id]}, s.coordinator)
    assert [g["person_id"] for g in r.json()["guides"]] == [s.guide2_id]
    assert s.get(f"/projects/{pid}", s.guide).status_code == 404  # the removed guide no longer sees it
    before = len(events("projects.guide.assigned", s.org.id))
    s.put(f"/projects/{pid}/guides", {"guide_ids": [s.guide2_id]}, s.coordinator)
    assert len(events("projects.guide.assigned", s.org.id)) == before  # nothing changed, nothing published
    r = s.put(f"/projects/{pid}/guides", {"guide_ids": [s.member_id]}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "member_is_guide"
    assert s.put(f"/projects/{pid}/guides", {"guide_ids": []}, s.coordinator).status_code == 422
    assert s.put(f"/projects/{pid}/guides", {"guide_ids": ["g1"]}, s.coordinator).status_code == 422


def test_cancel_a_proposed_or_active_project(studio):
    s = studio
    pid = s.project["id"]
    assert s.post(f"/projects/{pid}/cancel", {"reason": "no"}, s.coordinator).status_code == 422
    r = s.post(f"/projects/{pid}/cancel", {"reason": "Partner withdrew"}, s.coordinator)
    assert r.status_code == 200 and r.json()["status"] == "cancelled" and r.json()["reason"] == "Partner withdrew"
    assert events("projects.project.cancelled", s.org.id)[-1] == {
        "organisation_id": s.org.id,
        "project_id": pid,
        "reason": "Partner withdrew",
    }
    r = s.post(f"/projects/{pid}/cancel", {"reason": "Again"}, s.coordinator)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "invalid_status"
    for path, body in (
        (f"/projects/{pid}/members", {"person_id": new_id()}),
        (f"/projects/{pid}/milestones", {"title": "x", "due_on": "2026-12-01"}),
    ):
        assert s.post(path, body, s.coordinator).status_code == 409, path
    assert s.put(f"/projects/{pid}/guides", {"guide_ids": [s.guide2_id]}, s.coordinator).status_code == 409
    proposal = s.propose(s.outsider)
    assert s.post(f"/projects/{proposal['id']}/cancel", {"reason": "Duplicate"}, s.coordinator).json()["status"] == (
        "cancelled"
    )
    assert (s.coordinator_id, "project.cancelled") in audit(pid)
