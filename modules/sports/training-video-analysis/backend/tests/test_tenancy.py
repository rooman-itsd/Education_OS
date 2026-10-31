"""Cross-tenant leak test (module standard rule 11): one organisation never sees another's rows."""

from conftest import BASE
from eos_testing import assert_no_cross_tenant_leak


def seed(org) -> dict:
    p = org.plan()
    d = org.drill()
    s = org.session(plan_id=p["id"], drill_ids=[d["id"]], attendee_ids=["11111111-1111-1111-1111-111111111111"])
    v = org.video(session_id=s["id"])
    t = org.post(f"/videos/{v['id']}/drill-tags", {"drill_id": d["id"], "start_timestamp": 1, "end_timestamp": 9})
    a = org.annotation(v["id"])
    return {"plan": p, "drill": d, "session": s, "video": v, "tag": t, "annotation": a}


def test_no_cross_tenant_leak(client, org, other_org):
    a, b = seed(org), seed(other_org)
    token = lambda h: h["Authorization"].split(" ", 1)[1]  # noqa: E731
    for path in ("/plans", "/sessions", "/drills", "/videos"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(org.admin), token(other_org.admin))

    as_b = other_org.admin
    video = a["video"]["id"]
    for path in (
        f"/plans/{a['plan']['id']}",
        f"/drills/{a['drill']['id']}",
        f"/sessions/{a['session']['id']}",
        f"/videos/{video}",
        f"/videos/{video}/annotations",
        f"/videos/{video}/drill-tags",
        f"/videos/{video}/annotations/{a['annotation']['id']}",
        f"/videos/{b['video']['id']}/annotations/{a['annotation']['id']}",
    ):
        assert client.get(f"{BASE}{path}", headers=as_b).status_code == 404, path
    for path, body in (
        (f"/plans/{a['plan']['id']}", {"title": "x"}),
        (f"/drills/{a['drill']['id']}", {"title": "x"}),
        (f"/sessions/{a['session']['id']}", {"title": "x"}),
        (f"/videos/{video}", {"title": "x"}),
        (f"/videos/{video}/annotations/{a['annotation']['id']}", {"content": "x"}),
    ):
        assert client.patch(f"{BASE}{path}", json=body, headers=as_b).status_code == 404, path
    assert client.delete(f"{BASE}/videos/{video}/annotations/{a['annotation']['id']}", headers=as_b).status_code == 404
    note = {"author_id": other_org.admin_id, "start_timestamp": 1, "content": "x"}
    assert client.post(f"{BASE}/videos/{video}/annotations", json=note, headers=as_b).status_code == 404
    tag = {"drill_id": b["drill"]["id"], "start_timestamp": 1, "end_timestamp": 2}
    assert client.post(f"{BASE}/videos/{video}/drill-tags", json=tag, headers=as_b).status_code == 404

    # another organisation's ids are unknown here, so they cannot be referenced
    r = client.post(
        f"{BASE}/sessions",
        json={
            "plan_id": a["plan"]["id"],
            "coach_id": other_org.admin_id,
            "title": "x",
            "scheduled_start": "2026-10-29T01:00:00Z",
            "scheduled_end": "2026-10-29T02:00:00Z",
        },
        headers=as_b,
    )
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_plan"
    tag = {"drill_id": a["drill"]["id"], "start_timestamp": 1, "end_timestamp": 2}
    r = client.post(f"{BASE}/videos/{b['video']['id']}/drill-tags", json=tag, headers=as_b)
    assert r.status_code == 400 and r.json()["detail"]["code"] == "unknown_drill"
    # drill codes are unique per organisation, not globally
    assert a["drill"]["code"] == b["drill"]["code"]
