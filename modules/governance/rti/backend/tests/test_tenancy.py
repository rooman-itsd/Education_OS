"""Cross-tenant leak test (module standard rule 11): one organisation never sees or changes another's rows."""

from conftest import BASE, Desk, days
from eos_testing import assert_no_cross_tenant_leak


def token(headers: dict) -> str:
    return headers["Authorization"].split(" ", 1)[1]


def seed(desk: Desk) -> dict:
    r = desk.assigned(subject="Same subject in both organisations", received_on=days(-40))
    f = desk.ok(
        desk.post(f"/requests/{r['id']}/referrals", {"custodian_id": desk.custodian_id, "question": "A question?"})
    )
    return {"request": r["id"], "referral": f["id"]}


def test_no_cross_tenant_leak(client, org, other_org, clock, settings):
    settings(response_days=30)
    a, b = Desk(client, org), Desk(client, other_org)
    seed(a)
    seed(b)
    assert_no_cross_tenant_leak(client, f"{BASE}/requests", token(a.officer), token(b.officer), id_field="id")
    assert_no_cross_tenant_leak(client, f"{BASE}/referrals", token(a.officer), token(b.officer), id_field="id")
    assert_no_cross_tenant_leak(client, f"{BASE}/referrals", token(a.custodian), token(b.custodian), id_field="id")
    stats_a, stats_b = (
        a.ok(a.get("/stats/nearing-deadline", a.viewer)),
        b.ok(b.get("/stats/nearing-deadline", b.viewer)),
    )
    assert stats_a["overdue"] == stats_b["overdue"] == 1
    assert {i["request_id"] for i in stats_a["items"]}.isdisjoint({i["request_id"] for i in stats_b["items"]})


def test_numbers_are_per_organisation(client, org, other_org, clock, settings):
    settings(response_days=30)
    assert Desk(client, org).request()["number"] == Desk(client, other_org).request()["number"] == "RTI-000001"


def test_another_organisations_records_are_not_found(client, org, other_org, clock, settings):
    settings(response_days=30, appeal_window_days=30)
    a, b = Desk(client, org), Desk(client, other_org)
    ids = seed(a)
    rid, fid = ids["request"], ids["referral"]
    assert b.get(f"/requests/{rid}").status_code == 404
    assert b.patch(f"/requests/{rid}", {"subject": "Stolen subject"}).status_code == 404
    assert b.ok(b.get("/referrals"))["items"] == []
    assert b.get(f"/referrals?request_id={rid}").json()["items"] == []
    for path, body in [
        (f"/requests/{rid}/assign", {"officer_id": b.officer_id}),
        (f"/requests/{rid}/referrals", {"custodian_id": b.custodian_id, "question": "Stolen question?"}),
        (
            f"/requests/{rid}/respond",
            {
                "type": "refused",
                "summary": "No.",
                "grounds": "None.",
                "dispatched_on": days(0),
                "dispatch_mode": "post",
            },
        ),
        (f"/requests/{rid}/transfer", {"authority_name": "X", "transferred_on": days(0), "reason": "Stolen."}),
        (f"/requests/{rid}/close", None),
    ]:
        assert b.post(path, body).status_code == 404, path
    for path, body in [
        (f"/requests/{rid}/appeal", {"filed_on": days(0), "grounds": "Stolen."}),
        (f"/requests/{rid}/appeal-decision", {"outcome": "upheld", "decision_note": "Stolen.", "decided_on": days(0)}),
    ]:
        assert b.post(path, body, b.appellate).status_code == 404, path
    assert b.post(f"/referrals/{fid}/reply", {"reply": "Stolen"}, b.custodian).status_code == 404
    after = a.ok(a.get(f"/requests/{rid}"))
    assert (after["status"], after["subject"]) == ("assigned", "Same subject in both organisations")
    assert a.ok(a.get("/referrals"))["items"][0]["status"] == "open"
