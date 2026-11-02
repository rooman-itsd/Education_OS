"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE
from eos_core.db import new_id
from eos_testing import assert_no_cross_tenant_leak


def seed(org, learner: str) -> dict:
    f, s, r = org.setup()
    a = org.assess(learner, s, r)
    return {"framework": f, "skill": s, "rubric": r, "assessment": a}


def test_no_cross_tenant_leak(client, org, other_org):
    learner = new_id()  # the same person id in both organisations: nothing of one shows in the other
    a, b = seed(org, learner), seed(other_org, learner)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    for path in ("/frameworks", "/skills", "/rubrics", "/assessments"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(org.admin), token(other_org.admin))

    as_b = other_org.admin
    for path in (
        f"/frameworks/{a['framework']['id']}",
        f"/skills/{a['skill']['id']}",
        f"/rubrics/{a['rubric']['id']}",
        f"/assessments/{a['assessment']['id']}",
        f"/learners/{learner}/progress?framework_id={a['framework']['id']}",
    ):
        assert client.get(f"{BASE}{path}", headers=as_b).status_code == 404, path
    assert (
        client.patch(f"{BASE}/frameworks/{a['framework']['id']}", json={"title": "x"}, headers=as_b).status_code == 404
    )
    assert client.patch(f"{BASE}/skills/{a['skill']['id']}", json={"title": "x"}, headers=as_b).status_code == 404
    for action in ("verify", "void"):
        assert client.post(f"{BASE}/assessments/{a['assessment']['id']}/{action}", headers=as_b).status_code == 404

    # the learner's progress and timeline in B are B's only
    progress = client.get(f"{BASE}/learners/{learner}/progress", headers=as_b).json()
    assert progress["organisation_id"] == other_org.id
    assert [s["skill_id"] for s in progress["current_skills"]] == [b["skill"]["id"]]
    timeline = client.get(f"{BASE}/learners/{learner}/timeline", headers=as_b).json()
    assert [e["id"] for e in timeline["items"]] == [b["assessment"]["id"]]

    # another organisation's ids are unknown here, so they cannot be referenced
    steal = other_org.body(new_id(), a["skill"], b["rubric"])
    r = client.post(f"{BASE}/assessments", json=steal, headers=other_org.evaluator)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_skill"
    r = client.post(
        f"{BASE}/skills",
        json={**{k: a["skill"][k] for k in ("code", "title", "level_scale")}, "framework_id": a["framework"]["id"]},
        headers=as_b,
    )
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_framework"
    # codes are unique per organisation, not globally
    assert a["framework"]["code"] == b["framework"]["code"]
