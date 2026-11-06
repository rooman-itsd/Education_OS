"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows, and never
refers to them from its own."""

from conftest import BASE, Desk, days
from eos_core.db import new_id
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Desk, dict]:
    d = Desk(client, org)
    c = d.submitted_q()
    evidence = d.ok(
        d.post(
            f"/responses/{c['q']['id']}/evidence",
            {"title": "Report", "kind": "link", "url": "https://example.edu/r"},
            d.alice,
        )
    )
    item = d.action_item(cycle_id=c["cycle"]["id"], due_on=days(3))
    return d, {
        "framework": c["framework"]["id"],
        "metric": c["q"]["metric_id"],
        "cycle": c["cycle"]["id"],
        "q": c["q"]["id"],
        "n": c["n"]["id"],
        "evidence": evidence["id"],
        "item": item["id"],
    }


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, ids = seed(client, org)
    b, _ = seed(client, other_org)
    for path in ("/frameworks", "/cycles", "/responses", "/action-items", f"/frameworks/{ids['framework']}/metrics"):
        if "metrics" in path:  # the other organisation has no such framework: not found, never a list
            assert b.get(path).status_code == 404
            continue
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(a.coordinator), token(b.coordinator))
    for path in ("/responses", "/action-items"):  # a contributor's own view, too
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(a.alice), token(b.alice))
    stats_a, stats_b = a.ok(a.get("/stats/action-items")), b.ok(b.get("/stats/action-items"))
    assert stats_a["open"] == stats_b["open"] == 1
    assert {i["id"] for i in stats_a["soonest"]}.isdisjoint({i["id"] for i in stats_b["soonest"]})
    assert a.ok(a.get(f"/cycles/{ids['cycle']}"))["response_counts"]["submitted"] == 1
    assert b.get(f"/cycles/{ids['cycle']}").status_code == 404


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    own = b.collecting()  # B has live records of its own, so nothing here is a "no data" 404
    assert b.get(f"/cycles/{ids['cycle']}").status_code == 404
    assert b.get(f"/responses/{ids['q']}").status_code == 404
    assert b.get(f"/frameworks/{ids['framework']}/metrics").status_code == 404
    gets = [
        (f"/responses/{ids['q']}", b.coordinator),
        (f"/responses/{ids['q']}", b.viewer),
    ]
    for path, headers in gets:
        assert b.get(path, headers).status_code == 404, path
    body = {"decision": "accept"}
    writes = [
        ("PATCH", f"/frameworks/{ids['framework']}", {"name": "Stolen"}, b.coordinator),
        (
            "POST",
            f"/frameworks/{ids['framework']}/metrics",
            {"code": "X", "title": "X", "kind": "qualitative"},
            b.coordinator,
        ),
        ("PATCH", f"/metrics/{ids['metric']}", {"title": "Stolen"}, b.coordinator),
        ("PATCH", f"/cycles/{ids['cycle']}", {"name": "Stolen"}, b.coordinator),
        ("POST", f"/cycles/{ids['cycle']}/status", {"status": "collecting"}, b.coordinator),
        (
            "POST",
            f"/cycles/{ids['cycle']}/assignments",
            {"assignments": [{"metric_id": own["q"]["metric_id"], "owner_id": new_id(), "due_on": days(5)}]},
            b.coordinator,
        ),
        ("PUT", f"/responses/{ids['q']}", {"value": 1}, b.alice),
        ("POST", f"/responses/{ids['q']}/submit", None, b.alice),
        ("POST", f"/responses/{ids['q']}/review", body, b.coordinator),
        ("POST", f"/responses/{ids['q']}/evidence", {"title": "x", "kind": "link", "url": "https://e.edu"}, b.alice),
        ("DELETE", f"/responses/{ids['q']}/evidence/{ids['evidence']}", None, b.alice),
        ("PATCH", f"/action-items/{ids['item']}", {"title": "Stolen"}, b.coordinator),
        ("PATCH", f"/action-items/{ids['item']}", {"status": "in_progress"}, b.alice),
    ]
    for method, path, payload, headers in writes:
        r = b.client.request(method, BASE + path, json=payload, headers=headers)
        assert r.status_code == 404, (method, path, r.status_code)
    # A's data is untouched.
    assert a.ok(a.get(f"/responses/{ids['q']}"))["status"] == "submitted"
    assert a.ok(a.get(f"/cycles/{ids['cycle']}"))["name"] == "Annual quality report"
    assert [f["name"] for f in a.ok(a.get("/frameworks"))] == ["Test framework"]


def test_records_of_another_organisation_cannot_be_referred_to(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    own = b.collecting()
    codes = {}
    r = b.post(
        "/cycles",
        {"framework_id": ids["framework"], "name": "x", "period_start": "2025-04-01", "period_end": "2026-03-31"},
    )
    codes["cycle"] = (r.status_code, r.json()["detail"]["code"])
    r = b.post(
        f"/cycles/{own['cycle']['id']}/assignments",
        {"assignments": [{"metric_id": ids["metric"], "owner_id": b.alice_id, "due_on": days(5)}]},
    )
    codes["assignment"] = (r.status_code, r.json()["detail"]["code"])
    r = b.post("/action-items", {"title": "x", "owner_id": b.alice_id, "due_on": days(5), "cycle_id": ids["cycle"]})
    codes["item cycle"] = (r.status_code, r.json()["detail"]["code"])
    r = b.post("/action-items", {"title": "x", "owner_id": b.alice_id, "due_on": days(5), "metric_id": ids["metric"]})
    codes["item metric"] = (r.status_code, r.json()["detail"]["code"])
    assert codes == {
        "cycle": (422, "framework_not_found"),
        "assignment": (422, "metric_not_found"),
        "item cycle": (422, "cycle_not_found"),
        "item metric": (422, "metric_not_found"),
    }
    assert b.ok(b.get(f"/responses?cycle_id={ids['cycle']}"))["items"] == []
    assert b.ok(b.get(f"/action-items?cycle_id={ids['cycle']}"))["items"] == []
    assert b.ok(b.get(f"/cycles?framework_id={ids['framework']}")) == []
