"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Desk, days
from eos_testing import assert_no_cross_tenant_leak

ASSET = {"module": "asset-management", "entity": "asset", "id": "shared-asset"}


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Desk, dict]:
    d = Desk(client, org)
    contract = d.active(end_date=days(20), start_date=days(-300))
    item = d.item(contract["id"], reference=ASSET)
    eng = d.engagement(contract["id"], covered_item_id=item["id"])
    return d, {"contract": contract["id"], "item": item["id"], "engagement": eng["id"]}


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    for path in ("/contracts", "/engagements"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(a.viewer), token(b.viewer))
    stats_a = a.ok(a.get("/stats/contracts-expiring", a.viewer))
    stats_b = b.ok(b.get("/stats/contracts-expiring", b.viewer))
    assert stats_a["expiring_count"] == stats_b["expiring_count"] == 1
    query = f"/coverage?module={ASSET['module']}&entity={ASSET['entity']}&id={ASSET['id']}"
    assert len(a.ok(a.get(query, a.viewer))) == len(b.ok(b.get(query, b.viewer))) == 1


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    cid, eid = ids["contract"], ids["engagement"]
    assert b.get(f"/contracts/{cid}").status_code == 404
    assert b.get(f"/engagements/{eid}").status_code == 404
    for path, body in [
        (f"/contracts/{cid}/activate", {}),
        (f"/contracts/{cid}/terminate", {"reason": "Stolen", "effective_date": days(1)}),
        (f"/contracts/{cid}/renew", {"end_date": days(800)}),
        (f"/contracts/{cid}/covered-items", {"description": "Stolen"}),
    ]:
        assert b.post(path, body).status_code == 404, path
    assert b.patch(f"/contracts/{cid}", {"owner_id": b.manager_id}).status_code == 404
    assert b.delete(f"/contracts/{cid}/covered-items/{ids['item']}").status_code == 404
    assert b.patch(f"/engagements/{eid}", {"description": "Stolen"}, b.coordinator).status_code == 404
    assert b.post(f"/engagements/{eid}/status", {"status": "in_progress"}, b.coordinator).status_code == 404
    raise_in_a = {"contract_id": cid, "kind": "breakdown_call", "description": "Into A"}
    assert b.post("/engagements", raise_in_a, b.coordinator).status_code == 422  # A's contract is unknown to B
    # A's records are untouched.
    after = a.ok(a.get(f"/contracts/{cid}"))
    assert (after["status"], after["owner_id"], len(after["covered_items"])) == ("active", a.manager_id, 1)
    assert a.ok(a.get(f"/engagements/{eid}"))["status"] == "open"
