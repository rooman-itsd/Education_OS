"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Desk
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Desk, dict]:
    d = Desk(client, org)
    t = d.raise_ticket()
    d.ok(d.post(f"/tickets/{t['id']}/comments", {"visibility": "public", "body": "Hello"}, d.agent))
    link = d.ok(
        d.post(f"/tickets/{t['id']}/links", {"module": "maintenance", "entity": "ticket", "ref_id": "w"}, d.agent)
    )
    return d, {"ticket": t["id"], "link": link["id"]}


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    for path, ha, hb in [
        ("/queues", a.admin, b.admin),
        ("/categories", a.admin, b.admin),
        ("/tickets", a.lead, b.lead),
        ("/me/tickets", a.requester, b.requester),
    ]:
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(ha), token(hb))
    stats_a = a.ok(a.get("/stats/open-by-priority?scope=all", a.lead))
    stats_b = b.ok(b.get("/stats/open-by-priority?scope=all", b.lead))
    assert stats_a["total_open"] == stats_b["total_open"] == 1


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    tid = ids["ticket"]
    for path, headers in [(f"/tickets/{tid}", b.lead), (f"/me/tickets/{tid}", b.requester)]:
        assert b.get(path, headers).status_code == 404, path
    posts = [
        (f"/tickets/{tid}/assign", {"assignee_id": b.agent_id}, b.lead),
        (f"/tickets/{tid}/comments", {"visibility": "public", "body": "x"}, b.lead),
        (f"/tickets/{tid}/status", {"status": "in_progress"}, b.lead),
        (f"/tickets/{tid}/resolve", {"resolution_note": "Stolen"}, b.lead),
        (f"/tickets/{tid}/cancel", {"reason": "Stolen"}, b.lead),
        (f"/tickets/{tid}/links", {"module": "m", "entity": "e", "ref_id": "r"}, b.lead),
        (f"/me/tickets/{tid}/withdraw", {"reason": "Stolen"}, b.requester),
    ]
    for path, body, headers in posts:
        assert b.post(path, body, headers).status_code == 404, path
    assert b.patch(f"/tickets/{tid}", {"title": "Stolen title"}, b.lead).status_code == 404
    assert b.patch(f"/queues/{a.it['id']}", {"name": "Stolen"}, b.admin).status_code == 404
    body = {"name": "Stolen", "default_queue_id": a.it["id"], "default_priority": "low"}
    assert b.patch(f"/categories/{a.category['id']}", body, b.admin).status_code == 404
    assert b.post("/categories", {**body, "name": "Mine"}, b.admin).status_code == 422  # A's queue is unknown to B
    raise_in_a = {"category_id": a.category["id"], "title": "Steal", "description": "Into A"}
    assert b.post("/me/tickets", raise_in_a, b.requester).status_code == 422
    delete = client.delete(f"{BASE}/tickets/{tid}/links/{ids['link']}", headers=b.lead)
    assert delete.status_code == 404
    # A's ticket is untouched.
    after = a.ok(a.get(f"/tickets/{tid}", a.lead))
    assert (after["status"], after["title"], len(after["links"])) == ("in_progress", "Cannot sign in", 1)
