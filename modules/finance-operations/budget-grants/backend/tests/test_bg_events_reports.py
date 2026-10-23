"""Spend from procurement and payroll events, the budget-vs-spend report and certificate reminders (F6, R4, R6, X2, X3)."""

from datetime import date

from bg_support import BASE, TODAY, YEAR, approved_budget, grant, head, outbox
from eos_budget_grants.application import consumers, jobs
from eos_core.db import SessionLocal


def handle(name, payload):
    with SessionLocal() as db:
        return consumers.handle(db, name, payload)


def line_of(client, org, budget_id):
    return client.get(f"{BASE}/budgets/{budget_id}", headers=org.staff).json()["lines"][0]


def test_purchase_order_commitment_release_and_payment(client, org):
    b = approved_budget(client, org, {head(client, org)["id"]: "10000"}, year="2032-33")
    line = b["lines"][0]["id"]
    issued = {
        "organisation_id": org.id,
        "purchase_order_id": "PO-1",
        "number": "PO/1",
        "vendor_id": "V",
        "line_id": line,
        "total": "4000.00",
    }
    assert handle(consumers.PO_ISSUED, issued)["result"] == "committed"
    assert handle(consumers.PO_ISSUED, issued)["result"] == "ignored"  # repeated event
    after = line_of(client, org, b["id"])
    assert (after["committed"], after["spent"], after["available"]) == ("4000.00", "0.00", "6000.00")
    paid = {
        "organisation_id": org.id,
        "vendor_invoice_id": "VI-1",
        "purchase_order_id": "PO-1",
        "vendor_id": "V",
        "line_id": line,
        "amount": "2500.00",
        "paid_on": "2026-10-20",
    }
    assert handle(consumers.INVOICE_PAID, paid)["result"] == "spent"
    assert handle(consumers.INVOICE_PAID, paid)["result"] == "ignored"
    after = line_of(client, org, b["id"])
    assert (after["committed"], after["spent"], after["available"]) == ("1500.00", "2500.00", "6000.00")
    cancelled = {
        "organisation_id": org.id,
        "purchase_order_id": "PO-1",
        "line_id": line,
        "released_amount": "9999.00",
        "reason": "remainder closed",
    }
    r = handle(consumers.PO_CANCELLED, cancelled)
    assert r["result"] == "released" and r["released"] == "1500.00"  # never more than the order still holds
    assert handle(consumers.PO_CANCELLED, cancelled)["result"] == "ignored"
    after = line_of(client, org, b["id"])
    assert (after["committed"], after["spent"], after["available"]) == ("0.00", "2500.00", "7500.00")
    sources = {
        e["source"]["module"]
        for e in client.get(f"{BASE}/expenditures?line_id={line}", headers=org.staff).json()["items"]
    }
    assert sources == {"procurement"}
    entry = client.get(f"{BASE}/expenditures?line_id={line}&kind=actual", headers=org.staff).json()["items"][0]
    assert (
        client.post(f"{BASE}/expenditures/{entry['id']}/reverse", json={"reason": "x"}, headers=org.staff).status_code
        == 409
    )


def test_spend_on_grant_lines_from_events(client, org):
    g = grant(client, org, amount="1000.00")
    line = g["lines"][0]["id"]
    handle(
        consumers.PO_ISSUED, {"organisation_id": org.id, "purchase_order_id": "PO-G", "line_id": line, "total": "400"}
    )
    assert client.get(f"{BASE}/grants/{g['id']}", headers=org.research).json()["committed_total"] == "400.00"
    assert [e["percent"] for e in outbox("budget-grants.line.threshold-reached", org.id) if e["line_id"] == line] == [
        80
    ]


def test_payroll_is_charged_to_the_salary_head(client, org):
    salaries = head(client, org, "SALARIES", "Salaries")
    approved_budget(client, org, {salaries["id"]: "900000"})
    run = {
        "organisation_id": org.id,
        "run_id": "RUN-10",
        "period": "2026-10",
        "net_total": "300000.00",
        "paid_on": "2026-10-31",
    }
    assert handle(consumers.PAYROLL_PAID, run)["result"] == "spent"
    assert handle(consumers.PAYROLL_PAID, run)["result"] == "ignored"
    report = client.get(f"{BASE}/reports/budget-vs-spend?scope=budgets", headers=org.staff).json()
    assert {h["name"]: h["spent"] for h in report["by_head"]}["Salaries"] == "300000.00"
    early = {**run, "run_id": "RUN-1", "paid_on": "2020-01-31"}
    assert "no approved institution-wide budget" in handle(consumers.PAYROLL_PAID, early)["reason"]


def test_bad_events_are_ignored_with_a_reason(client, org):
    assert handle("someone.else.happened", {"organisation_id": org.id})["result"] == "ignored"
    assert handle(consumers.PO_ISSUED, {"purchase_order_id": "x"})["reason"] == "the event carries no organisation_id"
    assert handle(consumers.PO_ISSUED, {"organisation_id": org.id})["reason"].startswith("malformed payload")
    assert (
        "no line"
        in handle(
            consumers.PO_ISSUED, {"organisation_id": org.id, "purchase_order_id": "P", "line_id": "nope", "total": "1"}
        )["reason"]
    )


def test_events_act_only_in_their_own_organisation(client, org, other_org):
    b = approved_budget(client, org, {head(client, org)["id"]: "100"}, year="2033-34")
    r = handle(
        consumers.PO_ISSUED,
        {"organisation_id": other_org.id, "purchase_order_id": "PO-X", "line_id": b["lines"][0]["id"], "total": "10"},
    )
    assert r["result"] == "ignored"
    assert line_of(client, org, b["id"])["committed"] == "0.00"


def test_budget_vs_spend_report(client, org):
    h1, h2 = head(client, org, name="Equipment"), head(client, org, name="Consumables")
    b = approved_budget(client, org, {h1["id"]: "1000", h2["id"]: "500"}, year="2034-35")
    by = {x["budget_head_id"]: x["id"] for x in b["lines"]}
    client.post(
        f"{BASE}/expenditures",
        json={"line_id": by[h1["id"]], "amount": "300", "date": TODAY, "description": "x"},
        headers=org.staff,
    )
    g = grant(client, org, amount="2000.00")
    handle(
        consumers.PO_ISSUED,
        {"organisation_id": org.id, "purchase_order_id": "PO-R", "line_id": g["lines"][0]["id"], "total": "100"},
    )
    r = client.get(f"{BASE}/reports/budget-vs-spend?financial_year=2034-35&scope=budgets", headers=org.research).json()
    assert (r["allocated"], r["committed"], r["spent"]) == ("1500.00", "0.00", "300.00")
    assert [x["name"] for x in r["by_head"]] == ["Equipment", "Consumables"]
    assert r["grants"]["active"] >= 1 and r["grants"]["ucs_due_30_days"] == 0
    with_grants = client.get(f"{BASE}/reports/budget-vs-spend?financial_year=2034-35", headers=org.staff).json()
    assert with_grants["committed"] == "100.00" and with_grants["allocated"] != r["allocated"]
    assert client.get(f"{BASE}/reports/budget-vs-spend?financial_year=nonsense", headers=org.staff).status_code == 422
    assert client.get(f"{BASE}/reports/budget-vs-spend", headers=org.faculty).status_code == 403
    assert client.get(f"{BASE}/reports/budget-vs-spend", headers=org.admin).json()["financial_year"] == YEAR


def test_certificate_reminders_once_per_window(client, org):
    g = grant(client, org)  # first certificate due 2027-04-01
    with SessionLocal() as db:
        jobs.run_daily(db, date(2027, 2, 1))  # 59 days: no reminder
        jobs.run_daily(db, date(2027, 3, 3))  # 29 days: the 30-day reminder
        jobs.run_daily(db, date(2027, 3, 4))  # still the 30-day window: nothing new
        jobs.run_daily(db, date(2027, 3, 26))  # 6 days: the 7-day reminder
    mine = [
        e["days_left"] for e in outbox("budget-grants.utilisation-certificate.due", org.id) if e["grant_id"] == g["id"]
    ]
    assert mine == [29, 6]
