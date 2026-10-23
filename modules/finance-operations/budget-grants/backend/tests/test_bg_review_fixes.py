"""Regression tests for the defects an independent review found (D1-D7 and smaller items); each failed before its fix."""

from datetime import date

from bg_support import BASE, TODAY, YEAR, approved_budget, auth, grant, head, outbox
from eos_budget_grants.application import consumers, jobs
from eos_core.db import SessionLocal
from eos_core.security import create_token


def handle(name, payload):
    with SessionLocal() as db:
        return consumers.handle(db, name, payload)


def certify(client, org, g, period_from, period_to):
    uc = client.post(
        f"{BASE}/grants/{g['id']}/utilisation-certificates",
        json={"period_from": period_from, "period_to": period_to},
        headers=org.research,
    ).json()
    r = client.post(
        f"{BASE}/utilisation-certificates/{uc['id']}/decision", json={"decision": "approved"}, headers=org.manager
    )
    assert r.status_code == 200, r.text
    return uc


def test_d1_a_certificate_for_the_first_year_covers_its_due_date(client, org):
    g = grant(client, org)  # 2026-04-01 to 2028-03-31, yearly
    certify(client, org, g, "2026-04-01", "2027-03-31")
    assert client.get(f"{BASE}/grants/{g['id']}", headers=org.research).json()["next_uc_due"] == "2028-03-31"
    with SessionLocal() as db:
        jobs.run_daily(db, date(2027, 3, 20))
    assert [e for e in outbox("budget-grants.utilisation-certificate.due", org.id) if e["grant_id"] == g["id"]] == []


def _revision(g, lines, sanctioned, investigators):
    return {
        "code": g["code"],
        "title": g["title"],
        "funder": g["funder"],
        "sanctioned_amount": sanctioned,
        "start_date": g["start_date"],
        "end_date": g["end_date"],
        "investigators": investigators,
        "lines": lines,
    }


def test_d2_a_line_with_released_entries_is_never_deleted(client, org):
    g = grant(client, org, amount="1000.00")
    keep, drop = g["lines"][0], g["lines"][1]
    handle(
        consumers.PO_ISSUED,
        {"organisation_id": org.id, "purchase_order_id": "PO-D2", "line_id": drop["id"], "total": "100"},
    )
    handle(
        consumers.PO_CANCELLED,
        {"organisation_id": org.id, "purchase_order_id": "PO-D2", "line_id": drop["id"], "released_amount": "100"},
    )
    body = _revision(
        g,
        [{"budget_head_id": keep["budget_head_id"], "sanctioned": "1000"}],
        "1000.00",
        [{"user_id": org.ids["faculty"], "role": "principal"}],
    )
    r = client.put(f"{BASE}/grants/{g['id']}", json=body, headers=org.research)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "line_in_use"


def test_d3_a_line_is_never_revised_below_what_is_used(client, org):
    g = grant(client, org, amount="1000.00")
    a, b = g["lines"]
    client.post(
        f"{BASE}/expenditures",
        json={"line_id": a["id"], "amount": "300", "date": TODAY, "description": "x"},
        headers=org.staff,
    )
    pi = [{"user_id": org.ids["faculty"], "role": "principal"}]
    below = _revision(
        g,
        [
            {"budget_head_id": a["budget_head_id"], "sanctioned": "100"},
            {"budget_head_id": b["budget_head_id"], "sanctioned": "900"},
        ],
        "1000.00",
        pi,
    )
    r = client.put(f"{BASE}/grants/{g['id']}", json=below, headers=org.research)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "below_used"
    tight = _revision(
        g,
        [
            {"budget_head_id": a["budget_head_id"], "sanctioned": "350"},
            {"budget_head_id": b["budget_head_id"], "sanctioned": "650"},
        ],
        "1000.00",
        pi,
    )
    assert client.put(f"{BASE}/grants/{g['id']}", json=tight, headers=org.research).status_code == 200
    assert [
        e["percent"] for e in outbox("budget-grants.line.threshold-reached", org.id) if e["line_id"] == a["id"]
    ] == [80]


def test_d4_a_deactivated_head_does_not_block_revising_its_line(client, org):
    g = grant(client, org, amount="1000.00")
    a, b = g["lines"]
    h = client.get(f"{BASE}/budget-heads", headers=org.staff).json()
    head_a = next(x for x in h if x["id"] == a["budget_head_id"])
    client.put(
        f"{BASE}/budget-heads/{head_a['id']}",
        json={"code": head_a["code"], "name": head_a["name"], "active": False},
        headers=org.staff,
    )
    lines = [
        {"budget_head_id": a["budget_head_id"], "sanctioned": "500"},
        {"budget_head_id": b["budget_head_id"], "sanctioned": "500"},
    ]
    body = {
        **_revision(g, lines, "1000.00", [{"user_id": org.ids["faculty"], "role": "principal"}]),
        "title": "Renamed",
    }
    r = client.put(f"{BASE}/grants/{g['id']}", json=body, headers=org.research)
    assert r.status_code == 200 and r.json()["title"] == "Renamed"
    new = head(client, org)
    client.put(
        f"{BASE}/budget-heads/{new['id']}",
        json={"code": new["code"], "name": new["name"], "active": False},
        headers=org.staff,
    )
    with_new = {
        **body,
        "sanctioned_amount": "1001.00",
        "lines": [*lines, {"budget_head_id": new["id"], "sanctioned": "1"}],
    }
    assert client.put(f"{BASE}/grants/{g['id']}", json=with_new, headers=org.research).status_code == 422


def test_d5_a_returned_certificate_cannot_be_certified(client, org):
    g = grant(client, org)
    uc = client.post(
        f"{BASE}/grants/{g['id']}/utilisation-certificates",
        json={"period_from": "2026-04-01", "period_to": "2027-03-31"},
        headers=org.research,
    ).json()
    client.post(
        f"{BASE}/utilisation-certificates/{uc['id']}/decision", json={"decision": "returned"}, headers=org.manager
    )
    r = client.post(
        f"{BASE}/utilisation-certificates/{uc['id']}/decision", json={"decision": "approved"}, headers=org.manager
    )
    assert r.status_code == 409


def test_d6_whoever_edits_or_submits_a_budget_cannot_approve_it(client, org):
    h = head(client, org)
    body = {"financial_year": "2040-41", "lines": [{"budget_head_id": h["id"], "allocated": "100"}]}
    b = client.post(f"{BASE}/budgets", json=body, headers=org.staff).json()
    client.post(f"{BASE}/budgets/{b['id']}/submit", headers=org.staff)
    client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "returned"}, headers=org.manager)
    both = auth(create_token(user_id=org.ids["manager"], organisation_id=org.id, roles=["finance-staff", "management"]))
    client.put(
        f"{BASE}/budgets/{b['id']}",
        json={**body, "lines": [{"budget_head_id": h["id"], "allocated": "999999"}]},
        headers=both,
    )
    client.post(f"{BASE}/budgets/{b['id']}/submit", headers=both)
    assert (
        client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=both).status_code
        == 403
    )
    assert (
        client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=org.staff).status_code
        == 403
    )  # lacks approve
    second = auth(create_token(user_id="someone-else", organisation_id=org.id, roles=["management"]))
    assert (
        client.post(f"{BASE}/budgets/{b['id']}/decision", json={"decision": "approved"}, headers=second).status_code
        == 200
    )


def test_d7_malformed_events_are_ignored_never_raised(client, org):
    b = approved_budget(client, org, {head(client, org)["id"]: "100"}, year="2041-42")
    line = b["lines"][0]["id"]
    assert handle(consumers.PO_ISSUED, ["not", "an", "object"])["reason"] == "malformed payload: not an object"
    bad_id = handle(
        consumers.PO_ISSUED, {"organisation_id": org.id, "purchase_order_id": {"x": 1}, "line_id": line, "total": "1"}
    )
    assert bad_id["reason"].startswith("malformed payload")
    null_id = handle(
        consumers.PO_ISSUED, {"organisation_id": org.id, "purchase_order_id": None, "line_id": line, "total": "1"}
    )
    assert null_id["reason"].startswith("malformed payload")
    assert client.get(f"{BASE}/budgets/{b['id']}", headers=org.staff).json()["lines"][0]["committed"] == "0.00"


def test_strings_are_never_null(client, org):
    g = grant(client, org)
    client.post(
        f"{BASE}/grants/{g['id']}/funds-received",
        json={"amount": "10", "received_on": "2026-05-01"},
        headers=org.research,
    )
    full = client.get(f"{BASE}/grants/{g['id']}", headers=org.research).json()
    assert full["funds_received"][0]["reference"] == "" and all(i["name"] == "" for i in full["investigators"])


def test_dates_stay_inside_the_budget_year_or_grant_period(client, org):
    b = approved_budget(client, org, {head(client, org)["id"]: "100"}, year=YEAR)
    r = client.post(
        f"{BASE}/expenditures",
        json={"line_id": b["lines"][0]["id"], "amount": "1", "date": "2030-01-01", "description": "x"},
        headers=org.staff,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "date_outside_period"
    g = grant(client, org)
    outside = client.post(
        f"{BASE}/grants/{g['id']}/utilisation-certificates",
        json={"period_from": "2025-01-01", "period_to": "2026-12-31"},
        headers=org.research,
    )
    assert outside.status_code == 422 and outside.json()["detail"]["code"] == "outside_grant"
