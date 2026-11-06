"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import TICKET, Desk, days, rca_body
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Desk, dict]:
    d = Desk(client, org)
    incident = d.incident(affected_services=["Shared label"])
    reference = d.ok(d.post(f"/incidents/{incident['id']}/references", TICKET, d.responder))
    problem = d.problem(affected_services=["Shared label"])
    d.ok(d.patch(f"/incidents/{incident['id']}", {"problem_id": problem["id"]}, d.responder))
    d.ok(d.put(f"/problems/{problem['id']}/rca", rca_body()))
    action = d.action(problem["id"])
    ids = {"incident": incident["id"], "reference": reference["reference_id"], "problem": problem["id"]}
    return d, {**ids, "action": action["id"]}


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    for path in ("/incidents", "/problems", "/actions"):
        assert_no_cross_tenant_leak(client, f"/api/v1/incident-management{path}", token(a.viewer), token(b.viewer))
    assert a.ok(a.get("/stats/open", a.viewer))["total_open"] == b.ok(b.get("/stats/open", b.viewer))["total_open"] == 1
    assert len(a.ok(a.get("/incidents?service=Shared label"))["items"]) == 1
    assert a.ok(a.get("/incidents"))["items"][0]["number"] == b.ok(b.get("/incidents"))["items"][0]["number"]


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    iid, pid, aid = ids["incident"], ids["problem"], ids["action"]
    assert b.get(f"/incidents/{iid}").status_code == 404
    assert b.get(f"/problems/{pid}").status_code == 404
    assert b.get(f"/problems/{pid}/rca").status_code == 404
    for path, body in [
        (f"/incidents/{iid}/status", {"status": "investigating"}),
        (f"/incidents/{iid}/updates", {"body": "Stolen"}),
        (f"/incidents/{iid}/references", {**TICKET, "id": "other"}),
        (f"/problems/{pid}/status", {"status": "investigating"}),
        (f"/problems/{pid}/rca/publish", {}),
        (f"/problems/{pid}/actions", {"description": "Stolen", "owner_id": b.manager_id, "due_date": days(1)}),
    ]:
        assert b.post(path, body).status_code == 404, path
    assert b.patch(f"/incidents/{iid}", {"title": "Stolen"}).status_code == 404
    assert b.patch(f"/problems/{pid}", {"title": "Stolen"}).status_code == 404
    assert b.put(f"/problems/{pid}/rca", rca_body()).status_code == 404
    assert b.patch(f"/problems/{pid}/actions/{aid}", {"status": "done"}).status_code == 404
    assert b.delete(f"/incidents/{iid}/references/{ids['reference']}").status_code == 404
    own = b.incident()
    assert b.patch(f"/incidents/{own['id']}", {"problem_id": pid}, b.responder).status_code == 404  # A's problem
    own_problem = b.problem()
    assert b.patch(f"/problems/{own_problem['id']}/actions/{aid}", {"status": "done"}).status_code == 404
    # A's records are untouched.
    incident = a.ok(a.get(f"/incidents/{iid}"))
    assert (incident["status"], incident["title"], len(incident["references"]), incident["updates"]) == (
        "open",
        "Campus Wi-Fi down in block A",
        1,
        [],
    )
    problem = a.ok(a.get(f"/problems/{pid}"))
    assert (problem["status"], problem["rca_status"], problem["actions"][0]["status"]) == ("open", "draft", "open")
