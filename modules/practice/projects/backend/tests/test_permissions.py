"""Every operation refuses a caller without the permission the contract names (403, nothing changes), and a
bad id anywhere is a 422, never a stored row or a 500."""

import pytest
from conftest import BASE, events
from eos_projects.infrastructure.models import new_id


def calls(s, mid: str) -> list[tuple[str, str, dict | None]]:
    pid = s.project["id"]
    return [
        ("GET", "/projects", None),
        ("POST", "/projects", {"title": "x", "starts_on": "2026-08-01", "ends_on": "2027-04-30"}),
        ("GET", f"/projects/{pid}", None),
        ("PATCH", f"/projects/{pid}", {"title": "x"}),
        ("POST", f"/projects/{pid}/decision", {"decision": "rejected", "reason": "No thanks"}),
        ("POST", f"/projects/{pid}/members", {"person_id": new_id()}),
        ("DELETE", f"/projects/{pid}/members/{s.member_id}", None),
        ("PUT", f"/projects/{pid}/guides", {"guide_ids": [new_id()]}),
        ("POST", f"/projects/{pid}/cancel", {"reason": "Stop it"}),
        ("GET", f"/projects/{pid}/milestones", None),
        ("POST", f"/projects/{pid}/milestones", {"title": "x", "due_on": "2027-01-01"}),
        ("PATCH", f"/milestones/{mid}", {"title": "x"}),
        ("GET", f"/milestones/{mid}/submissions", None),
        ("POST", f"/milestones/{mid}/submissions", {"note": "x"}),
        ("POST", f"/milestones/{mid}/review", {"decision": "accepted"}),
        ("POST", f"/projects/{pid}/submit", {"note": "x"}),
        ("POST", f"/projects/{pid}/evaluation", {"decision": "returned"}),
        ("GET", "/me/projects", None),
        ("GET", "/me/milestones", None),
        ("GET", "/me/reviews", None),
    ]


# The operations each generic role may NOT call at all (by method and path template).
REFUSED = {
    "projects-member": {
        "GET /projects",
        "POST /projects/{id}/decision",
        "PUT /projects/{id}/guides",
        "POST /projects/{id}/cancel",
        "POST /projects/{id}/milestones",
        "PATCH /milestones/{id}",
        "POST /milestones/{id}/review",
        "POST /projects/{id}/evaluation",
        "GET /me/reviews",
    },
    "projects-guide": {
        "POST /projects",
        "PATCH /projects/{id}",
        "POST /projects/{id}/decision",
        "POST /projects/{id}/members",
        "DELETE /projects/{id}/members/{person_id}",
        "PUT /projects/{id}/guides",
        "POST /projects/{id}/cancel",
        "POST /milestones/{id}/submissions",
        "POST /projects/{id}/submit",
        "GET /me/projects",
        "GET /me/milestones",
    },
    "projects-coordinator": {
        "POST /milestones/{id}/submissions",
        "POST /milestones/{id}/review",
        "POST /projects/{id}/submit",
        "POST /projects/{id}/evaluation",
        "GET /me/projects",
        "GET /me/milestones",
        "GET /me/reviews",
    },
    "projects-viewer": {
        "POST /projects",
        "PATCH /projects/{id}",
        "POST /projects/{id}/decision",
        "POST /projects/{id}/members",
        "DELETE /projects/{id}/members/{person_id}",
        "PUT /projects/{id}/guides",
        "POST /projects/{id}/cancel",
        "POST /projects/{id}/milestones",
        "PATCH /milestones/{id}",
        "POST /milestones/{id}/submissions",
        "POST /milestones/{id}/review",
        "POST /projects/{id}/submit",
        "POST /projects/{id}/evaluation",
        "GET /me/projects",
        "GET /me/milestones",
        "GET /me/reviews",
    },
}


def template(s, mid: str, method: str, path: str) -> str:
    path = path.replace(s.project["id"], "{id}").replace(mid, "{id}").replace(s.member_id, "{person_id}")
    return f"{method} {path}"


@pytest.mark.parametrize("role", sorted(REFUSED))
def test_each_role_is_refused_what_it_does_not_hold(studio, client, role):
    s = studio
    mid = s.milestone()["id"]
    _, headers = s.org.user(role)
    before = len(events("projects.project.cancelled", s.org.id))
    refused = set()
    for method, path, body in calls(s, mid):
        r = client.request(method, f"{BASE}{path}", json=body, headers=headers)
        if r.status_code == 403 and "requires" in str(r.json()["detail"]):
            refused.add(template(s, mid, method, path))
    assert refused == REFUSED[role]
    if "POST /projects/{id}/cancel" in refused:  # a refused call changes nothing
        assert len(events("projects.project.cancelled", s.org.id)) == before
        assert s.get(f"/projects/{s.project['id']}", s.coordinator).json()["status"] == "active"


def test_a_user_with_no_projects_role_is_refused_everything(studio, client):
    s = studio
    mid = s.milestone()["id"]
    _, nobody = s.org.user("applicant")
    for method, path, body in calls(s, mid):
        assert client.request(method, f"{BASE}{path}", json=body, headers=nobody).status_code == 403, path
    assert client.get(f"{BASE}/me/projects").status_code == 401


def test_bad_ids_are_422(studio, client):
    s = studio
    pid = s.project["id"]
    assert s.get("/projects/not-a-uuid", s.coordinator).status_code == 422
    assert s.patch("/milestones/42", {"title": "x"}, s.guide).status_code == 422
    assert s.delete(f"/projects/{pid}/members/someone", s.coordinator).status_code == 422
    assert s.post(f"/projects/{pid}/members", {"person_id": "someone"}, s.coordinator).status_code == 422
    body = {"title": "x", "starts_on": "2026-08-01", "ends_on": "2027-04-30", "member_ids": ["a"], "lead_id": "a"}
    assert s.post("/projects", body, s.coordinator).status_code == 422
    assert (
        s.post(f"/projects/{pid}/decision", {"decision": "approved", "guide_ids": ["g"]}, s.coordinator).status_code
        == 422
    )
    # Unknown but well-formed ids are 404.
    assert s.get(f"/projects/{new_id()}", s.coordinator).status_code == 404
    assert s.patch(f"/milestones/{new_id()}", {"title": "x"}, s.guide).status_code == 404


def test_inputs_are_bounded(studio):
    s = studio
    base = {"starts_on": "2026-08-01", "ends_on": "2027-04-30"}
    for over in (
        {"title": "x" * 201},
        {"title": "x", "summary": "x" * 4001},
        {"title": "x", "kind": "x" * 101},
        {"title": "x", "academic_year": "x" * 21},
        {"title": "x", "external_partner": "x" * 201},
        {"title": "x", "unknown": 1},
        {"title": "x", "member_ids": [new_id() for _ in range(51)]},
    ):
        assert s.post("/projects", {**base, **over}, s.coordinator).status_code == 422, list(over)
    mid = s.milestone()["id"]
    many = [new_id() for _ in range(21)]
    assert s.post(f"/milestones/{mid}/submissions", {"note": "x", "document_ids": many}, s.member).status_code == 422
    assert s.post(f"/projects/{s.project['id']}/cancel", {"reason": "x" * 2001}, s.coordinator).status_code == 422
    assert s.get("/projects?q=" + "x" * 201, s.coordinator).status_code == 422
    assert s.get("/me/reviews?limit=0", s.guide).status_code == 422
