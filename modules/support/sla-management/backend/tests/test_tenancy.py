"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Desk
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(client, org) -> tuple[Desk, dict]:
    d = Desk(client, org)
    cal = d.calendar()
    policy = d.policy(cal["id"])
    ticket = d.ticket()
    clock = d.clocks(ticket)["response"]
    return d, {"calendar": cal["id"], "policy": policy["id"], "ticket": ticket, "clock": clock["id"]}


def test_no_cross_tenant_leak(client, org, other_org, clock):
    a, _ = seed(client, org)
    b, _ = seed(client, other_org)
    for path in ("/calendars", "/policies", "/clocks"):
        assert_no_cross_tenant_leak(client, f"{BASE}{path}", token(a.viewer), token(b.viewer))
    page_a = a.ok(a.get("/clocks", a.viewer))["items"]
    page_b = b.ok(b.get("/clocks", b.viewer))["items"]
    assert {c["organisation_id"] for c in page_a} == {org.id}
    assert {c["organisation_id"] for c in page_b} == {other_org.id}
    assert not {c["id"] for c in page_a} & {c["id"] for c in page_b}


def test_another_organisations_records_are_not_found(client, org, other_org, clock):
    a, ids = seed(client, org)
    b = Desk(client, other_org)
    assert b.get(f"/calendars/{ids['calendar']}").status_code == 404
    assert b.get(f"/policies/{ids['policy']}").status_code == 404
    assert b.get(f"/clocks/{ids['clock']}").status_code == 404
    assert b.get(f"/tickets/{ids['ticket']}").status_code == 404
    assert b.patch(f"/calendars/{ids['calendar']}", {"active": False}).status_code == 404
    assert b.patch(f"/policies/{ids['policy']}", {"active": False}).status_code == 404
    using_a = {
        "name": "Into A",
        "priority": "low",
        "calendar_id": ids["calendar"],
        "response_target_minutes": 10,
        "resolution_target_minutes": 20,
    }
    refused = b.post("/policies", using_a)  # A's calendar is unknown to B
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "unknown_calendar")
    stats = b.ok(b.get("/stats/breaches"))
    assert (stats["breached_open"], stats["most_overdue"]) == (0, [])
    # A's records are untouched.
    assert a.ok(a.get(f"/calendars/{ids['calendar']}"))["active"] is True
    assert a.ok(a.get(f"/policies/{ids['policy']}"))["active"] is True
