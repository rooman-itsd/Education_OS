"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Desk, days
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Desk, dict]:
    d = Desk(client, org)
    ob = d.obligation(title="Shared title in both organisations")
    f = d.filing(ob["id"], due_on=days(5))
    return d, {"obligation": ob["id"], "filing": f["id"]}


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    assert_no_cross_tenant_leak(client, f"{BASE}/obligations", token(a.viewer), token(b.viewer))
    assert_no_cross_tenant_leak(client, f"{BASE}/filings", token(a.viewer), token(b.viewer), id_field="id")
    due_a = a.ok(a.get("/stats/due?scope=all", a.viewer))
    due_b = b.ok(b.get("/stats/due?scope=all", b.viewer))
    assert due_a["due_soon"] == due_b["due_soon"] == 1
    assert len(a.ok(a.get(f"/calendar?from={days(0)}&to={days(30)}", a.viewer))["items"]) == 1


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    oid, fid = ids["obligation"], ids["filing"]
    assert b.get(f"/obligations/{oid}").status_code == 404
    assert b.get(f"/filings/{fid}").status_code == 404
    assert b.patch(f"/obligations/{oid}", {"title": "Stolen"}).status_code == 404
    assert b.patch(f"/filings/{fid}", {"due_on": days(40)}).status_code == 404
    period = {"period_label": "Stolen", "period_start": days(-60), "period_end": days(-30), "due_on": days(10)}
    assert b.post(f"/obligations/{oid}/filings", period).status_code == 404
    for path, body in [
        (f"/filings/{fid}/status", {"status": "not_applicable", "reason": "Stolen"}),
        (f"/filings/{fid}/submit", {"submitted_on": days(0), "submission_reference": "X"}),
        (f"/filings/{fid}/acknowledge", {"acknowledged_on": days(0)}),
    ]:
        assert b.post(path, body).status_code == 404, path
    after = a.ok(a.get(f"/filings/{fid}"))
    assert (after["status"], after["due_on"]) == ("open", days(5))
