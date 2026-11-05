"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Studio
from eos_projects.infrastructure.models import new_id
from eos_testing import assert_no_cross_tenant_leak


def seed(client, org) -> tuple[Studio, dict]:
    s = Studio(client, org)
    m = s.milestone()
    s.submit(m["id"])
    final = s.new_project("Final work")
    s.post(f"/projects/{final['id']}/submit", {"note": "Final"}, s.lead)
    proposal = s.propose(s.outsider)
    return s, {"milestone": m["id"], "final": final["id"], "proposal": proposal["id"]}


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def test_no_cross_tenant_leak(client, org, other_org):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    lists = [
        ("/projects", a.viewer, b.viewer),
        ("/projects?status=active", a.guide, b.guide),
        ("/me/projects", a.lead, b.lead),
        ("/me/milestones", a.member, b.member),
    ]
    for path, ha, hb in lists:
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))
    # /me/reviews rows carry no organisation_id of their own: compare the projects and submissions instead.
    ra = client.get(f"{BASE}/me/reviews", headers=a.guide).json()
    rb = client.get(f"{BASE}/me/reviews", headers=b.guide).json()
    assert ra and rb
    assert {r["submission"]["organisation_id"] for r in ra} == {a.org.id}
    assert {r["submission"]["organisation_id"] for r in rb} == {b.org.id}
    assert not {r["project_id"] for r in ra} & {r["project_id"] for r in rb}


def test_another_organisations_records_are_not_found(client, org, other_org):
    a, ids = seed(client, org)
    b = Studio(client, other_org)
    pid, mid = a.project["id"], ids["milestone"]
    for path in (f"/projects/{pid}", f"/projects/{pid}/milestones", f"/milestones/{mid}/submissions"):
        assert client.get(f"{BASE}{path}", headers=b.viewer).status_code == 404, path
    posts = [
        (f"/projects/{ids['proposal']}/decision", {"decision": "rejected", "reason": "steal"}, b.coordinator),
        (f"/projects/{pid}/members", {"person_id": new_id()}, b.coordinator),
        (f"/projects/{pid}/cancel", {"reason": "steal"}, b.coordinator),
        (f"/projects/{pid}/milestones", {"title": "x", "due_on": "2027-01-01"}, b.coordinator),
        (f"/milestones/{mid}/submissions", {"note": "x"}, b.member),
        (f"/milestones/{mid}/review", {"decision": "accepted"}, b.guide),
        (f"/projects/{pid}/submit", {"note": "x"}, b.member),
        (f"/projects/{ids['final']}/evaluation", {"decision": "returned"}, b.guide),
    ]
    for path, body, headers in posts:
        assert client.post(f"{BASE}{path}", json=body, headers=headers).status_code == 404, path
    assert client.patch(f"{BASE}/projects/{pid}", json={"title": "x"}, headers=b.coordinator).status_code == 404
    assert client.patch(f"{BASE}/milestones/{mid}", json={"title": "x"}, headers=b.coordinator).status_code == 404
    assert (
        client.put(f"{BASE}/projects/{pid}/guides", json={"guide_ids": [new_id()]}, headers=b.coordinator).status_code
        == 404
    )
    assert client.delete(f"{BASE}/projects/{pid}/members/{a.member_id}", headers=b.coordinator).status_code == 404
    # B's filters by A's people find nothing; A's project is unchanged.
    assert client.get(f"{BASE}/projects?member_id={a.lead_id}", headers=b.viewer).json()["items"] == []
    detail = client.get(f"{BASE}/projects/{pid}", headers=a.viewer).json()
    assert detail["status"] == "active" and detail["member_count"] == 2 and detail["title"] == "Solar irrigation pump"
