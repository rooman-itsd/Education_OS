"""Which projects keys each role holds, read the way the platform reads them (eos_core.config.permissions_for), and
that real tokens of profile roles work through their layout's `module_roles`."""

from eos_core.config import permissions_for

MEMBER = {"projects:self:read", "projects:self:propose", "projects:self:submit"}
GUIDE = {"projects:guidance:read", "projects:milestone:manage", "projects:review:record"}
COORDINATOR = {"projects:project:read", "projects:project:manage"}
VIEWER = {"projects:project:read"}


def projects_keys(roles: list[str]) -> set[str]:
    return {p for p in permissions_for(roles) if p.startswith("projects:")}


def test_generic_roles_get_exactly_their_grants():
    assert projects_keys(["projects-member"]) == MEMBER
    assert projects_keys(["projects-guide"]) == GUIDE
    assert projects_keys(["projects-coordinator"]) == COORDINATOR
    assert projects_keys(["projects-viewer"]) == VIEWER
    assert projects_keys(["projects-guide", "projects-coordinator"]) == GUIDE | COORDINATOR
    assert projects_keys(["applicant"]) == set()


def test_profile_roles_hold_the_module_roles_their_layouts_list():
    # engineering-student lists projects-member, project-guide lists projects-guide (platform/identity layouts).
    assert projects_keys(["engineering-student"]) == MEMBER
    assert projects_keys(["project-guide"]) == GUIDE


def test_a_profile_learner_token_proposes_and_sees_own_projects(studio):
    s = studio
    learner_id, learner = s.org.user("engineering-student")
    p = s.propose(learner)
    assert p["lead_id"] == learner_id
    assert [x["id"] for x in s.get("/me/projects", learner).json()] == [p["id"]]
    assert s.get("/projects", learner).status_code == 403


def test_a_profile_guide_token_sees_work_to_review(studio):
    s = studio
    guide_id, guide = s.org.user("project-guide")
    s.put(f"/projects/{s.project['id']}/guides", {"guide_ids": [guide_id]}, s.coordinator)
    r = s.post(f"/projects/{s.project['id']}/milestones", {"title": "Review", "due_on": "2026-12-01"}, guide)
    assert r.status_code == 201
    s.submit(r.json()["id"])
    assert [x["kind"] for x in s.get("/me/reviews", guide).json()] == ["milestone"]
    assert [x["id"] for x in s.get("/projects?status=active", guide).json()["items"]] == [s.project["id"]]
