"""Every state change leaves an audit record (PRD rule; the audit SDK does not exist yet), plus the close guard and
the amount limit."""

from bg_support import BASE, Org, approved_budget, grant, head
from eos_budget_grants.application import consumers
from eos_budget_grants.infrastructure.models import AuditEntry
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from sqlalchemy import select


def actions(org: Org) -> list[tuple[str, str | None]]:
    with SessionLocal() as db, platform_scope():
        q = (
            select(AuditEntry)
            .where(AuditEntry.organisation_id == org.id)
            .order_by(AuditEntry.occurred_at, AuditEntry.id)
        )
        return [(a.action, a.actor) for a in db.scalars(q)]


def test_every_state_change_is_audited(client, org):
    h1, h2 = head(client, org), head(client, org)
    client.put(f"{BASE}/budget-heads/{h1['id']}", json={"code": h1["code"], "name": "Renamed"}, headers=org.staff)
    body = {
        "financial_year": "2050-51",
        "lines": [{"budget_head_id": h1["id"], "allocated": "100"}, {"budget_head_id": h2["id"], "allocated": "100"}],
    }
    b = client.post(f"{BASE}/budgets", json=body, headers=org.staff).json()
    client.put(f"{BASE}/budgets/{b['id']}", json=body, headers=org.staff)
    client.post(f"{BASE}/budgets/{b['id']}/submit", headers=org.staff)
    client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    src, dst = (x["id"] for x in client.get(f"{BASE}/budgets/{b['id']}", headers=org.staff).json()["lines"])
    r = client.post(
        f"{BASE}/reappropriations",
        json={"from_line_id": src, "to_line_id": dst, "amount": "10", "reason": "x"},
        headers=org.staff,
    ).json()
    client.post(f"{BASE}/reappropriations/{r['id']}/decision", json={"decision": "rejected"}, headers=org.manager)
    e = client.post(
        f"{BASE}/expenditures",
        json={"line_id": src, "amount": "5", "date": "2050-06-01", "description": "x"},
        headers=org.staff,
    ).json()
    client.post(f"{BASE}/expenditures/{e['id']}/reverse", json={"reason": "x"}, headers=org.staff)
    g = grant(client, org, amount="1000.00")
    client.post(
        f"{BASE}/grants/{g['id']}/funds-received",
        json={"amount": "100", "received_on": "2026-05-01"},
        headers=org.research,
    )
    uc = client.post(
        f"{BASE}/grants/{g['id']}/utilisation-certificates",
        json={"period_from": "2026-04-01", "period_to": "2027-03-31"},
        headers=org.research,
    ).json()
    client.post(
        f"{BASE}/utilisation-certificates/{uc['id']}/decision", json={"decision": "approved"}, headers=org.manager
    )
    client.post(f"{BASE}/utilisation-certificates/{uc['id']}/mark-submitted", headers=org.research)
    with SessionLocal() as db:
        consumers.handle(
            db,
            consumers.PO_ISSUED,
            {"organisation_id": org.id, "purchase_order_id": "PO-A", "line_id": dst, "total": "1"},
        )
    client.post(f"{BASE}/grants/{g['id']}/close", json={"unspent_action": "returned"}, headers=org.research)

    got = actions(org)
    names = [a for a, _ in got]
    for expected in (
        "budget_head.created",
        "budget_head.updated",
        "budget.created",
        "budget.updated",
        "budget.submitted",
        "budget.approved",
        "reappropriation.requested",
        "reappropriation.rejected",
        "expenditure.actual",
        "expenditure.reversed",
        "grant.sanctioned",
        "grant.funds_received",
        "certificate.drafted",
        "certificate.approved",
        "certificate.submitted",
        "expenditure.commitment",
        "grant.closed",
    ):
        assert expected in names, expected
    assert ("budget.approved", org.ids["manager"]) in got
    assert ("expenditure.commitment", None) in got  # recorded from another module's event


def test_a_grant_with_open_commitments_is_not_closed(client, org):
    g = grant(client, org, amount="1000.00")
    line = g["lines"][0]["id"]
    with SessionLocal() as db:
        consumers.handle(
            db,
            consumers.PO_ISSUED,
            {"organisation_id": org.id, "purchase_order_id": "PO-C", "line_id": line, "total": "50"},
        )
    r = client.post(f"{BASE}/grants/{g['id']}/close", json={"unspent_action": "none"}, headers=org.research)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "open_commitments"
    with SessionLocal() as db:
        consumers.handle(
            db,
            consumers.PO_CANCELLED,
            {"organisation_id": org.id, "purchase_order_id": "PO-C", "line_id": line, "released_amount": "50"},
        )
    assert (
        client.post(f"{BASE}/grants/{g['id']}/close", json={"unspent_action": "none"}, headers=org.research).status_code
        == 200
    )


def test_amounts_never_exceed_the_column(client, org):
    b = approved_budget(client, org, {head(client, org)["id"]: "100"}, year="2051-52")
    r = client.post(
        f"{BASE}/expenditures",
        json={"line_id": b["lines"][0]["id"], "amount": "1000000000000", "date": "2051-06-01", "description": "x"},
        headers=org.staff,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_amount"
    big = {
        "financial_year": "2052-53",
        "lines": [{"budget_head_id": head(client, org)["id"], "allocated": "999999999999.99"}],
    }
    assert client.post(f"{BASE}/budgets", json=big, headers=org.staff).status_code == 201  # the largest that fits
