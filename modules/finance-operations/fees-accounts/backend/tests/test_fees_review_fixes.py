"""Regression tests for the defects an independent review found; each failed before its fix."""

from decimal import Decimal

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_fees_accounts.application import consumers
from eos_fees_accounts.domain import rules
from fees_support import BASE, TODAY, adhoc, head, pay_cash, published


def handle(name, payload):
    with SessionLocal() as db:
        return consumers.handle(db, name, payload)


def test_handlers_refuse_to_run_inside_platform_scope(client, org):
    with SessionLocal() as db, platform_scope(), pytest.raises(RuntimeError):
        consumers.handle(
            db, consumers.FINE_RAISED, {"organisation_id": org.id, "fine_id": "F", "person_id": "p", "amount": "1"}
        )


def test_one_session_handles_events_of_two_organisations(client, org, other_org):
    a = adhoc(client, org, "100.00")
    b = adhoc(client, other_org, "200.00")
    with SessionLocal() as db:
        ignored = consumers.handle(db, consumers.FINE_WAIVED, {"organisation_id": org.id, "fine_id": "none"})
        assert ignored["result"] == "ignored"
        for inv, o, ref in ((a, org, "R-A"), (b, other_org, "R-B")):
            event = {
                "organisation_id": o.id,
                "reference": ref,
                "source_module": "fees-accounts",
                "source_reference": inv["id"],
                "amount": inv["balance"],
            }
            assert consumers.handle(db, consumers.PAYMENT_SUCCEEDED, event)["result"] == "applied"


def test_hostel_and_transport_events_need_their_selector(client, org):
    published(client, org)  # an ordinary tuition structure, no room type or route
    hostel = {"organisation_id": org.id, "allocation_id": "A-X", "person_id": "p", "academic_year": "2026-27"}
    assert handle(consumers.ALLOCATION_CONFIRMED, hostel)["reason"] == "the allocation carries no room_type"
    bus = {"organisation_id": org.id, "pass_id": "P-X", "person_id": "p", "rider_type": "student"}
    assert handle(consumers.PASS_ISSUED, bus)["reason"] == "the pass carries no route_id"
    assert client.get(f"{BASE}/invoices?person_id=p", headers=org.staff).json()["items"] == []


def test_a_fully_refunded_invoice_can_be_cancelled(client, org):
    inv = adhoc(client, org, "500.00")
    p = pay_cash(client, org, inv["id"], "500.00")
    client.post(f"{BASE}/payments/{p['id']}/refunds", json={"amount": "500", "reason": "withdrawn"}, headers=org.staff)
    r = client.post(f"{BASE}/invoices/{inv['id']}/cancel", json={"reason": "withdrawn"}, headers=org.staff)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"


def test_zero_percent_instalments_split_exactly():
    assert rules.split_item(Decimal("100.01"), [Decimal(50), Decimal(50), Decimal(0)]) == [
        Decimal("50.01"),
        Decimal("50.00"),
        Decimal("0.00"),
    ]
    for amount in ("0.01", "0.03", "99.99", "12345.67"):
        for percents in ([33, 33, 34], [0, 100], [100, 0], [12.5, 12.5, 75], [1, 0, 99]):
            shares = rules.split_item(Decimal(amount), [Decimal(str(x)) for x in percents])
            assert sum(shares) == Decimal(amount) and all(s >= 0 for s in shares)


def test_an_event_skips_an_empty_instalment(client, org):
    h = head(client, org, "HOSTEL0", "hostel")
    published(
        client,
        org,
        [h],
        room_type="triple",
        instalments=[
            {"label": "All", "percent": 100, "due_date": "2026-11-01"},
            {"label": "None", "percent": 0, "due_date": "2027-01-01"},
        ],
    )
    event = {
        "organisation_id": org.id,
        "allocation_id": "A-0",
        "person_id": "p0",
        "room_type": "triple",
        "academic_year": "2026-27",
    }
    r = handle(consumers.ALLOCATION_CONFIRMED, event)
    assert r["result"] == "invoiced" and len(r["invoices"]) == 1


def test_a_concession_survives_a_voided_payment(client, org):
    inv = adhoc(client, org, "1000.00")
    p = client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={"amount": "600", "mode": "cheque", "paid_on": "2026-10-22"},
        headers=org.staff,
    ).json()
    cid = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "scholarship", "percent": 50, "reason": "merit"},
        headers=org.staff,
    ).json()["id"]
    client.post(f"{BASE}/concessions/{cid}/decision", json={"decision": "approved"}, headers=org.manager)
    client.post(f"{BASE}/payments/{p['id']}/void", json={"reason": "bounced"}, headers=org.staff)
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()["balance"] == "500.00"


def test_statement_and_dues_agree_after_a_refund(client, org):
    inv = adhoc(client, org, "500.00", person="p-agree")
    p = pay_cash(client, org, inv["id"], "500.00")
    client.post(f"{BASE}/payments/{p['id']}/refunds", json={"amount": "500", "reason": "x"}, headers=org.staff)
    statement = client.get(f"{BASE}/accounts/p-agree/statement", headers=org.staff).json()
    dues = client.get(f"{BASE}/dues?person_id=p-agree", headers=org.staff).json()
    assert statement["closing_balance"] == dues["balance"] == "500.00"


def test_refund_events_complete_only_a_requested_refund(client, org):
    assert (
        handle(consumers.PAYMENT_REFUNDED, {"organisation_id": org.id, "source_module": "fees-accounts"})["reason"]
        == "the event carries no refund_id"
    )


def test_concession_percent_has_two_decimals_and_targets_are_checked(client, org):
    inv = adhoc(client, org, "100.00")
    r = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "other", "percent": 12.345, "reason": "x"},
        headers=org.staff,
    )
    assert r.status_code == 422
    dup = {
        "academic_year": "2026-27",
        "targets": [{"period": "2026-10", "amount": "1"}, {"period": "2026-10", "amount": "2"}],
    }
    assert client.put(f"{BASE}/collection-targets", json=dup, headers=org.manager).status_code == 422
    foreign = {"academic_year": "2026-27", "targets": [{"period": "2026-10", "amount": "1", "fee_head_id": "not-ours"}]}
    assert client.put(f"{BASE}/collection-targets", json=foreign, headers=org.manager).status_code == 422


# ---------------------------------------------------------------- second review (F1-F7)


def succeeded(org, inv, reference, amount, currency="INR") -> dict:
    return {
        "organisation_id": org.id,
        "reference": reference,
        "purpose": "fee",
        "source_module": "fees-accounts",
        "source_reference": inv["id"],
        "amount": amount,
        "currency": currency,
        "completed_at": "2026-10-22T09:00:00+00:00",
    }


def test_a_refund_started_at_the_adapter_is_recorded(client, org):  # F1
    inv = adhoc(client, org, "800.00")
    handle(consumers.PAYMENT_SUCCEEDED, succeeded(org, inv, "ADP1", "800.00"))
    refunded = {
        "organisation_id": org.id,
        "reference": "ADP1",
        "purpose": "fee",
        "source_module": "fees-accounts",
        "source_reference": inv["id"],
        "refund_id": "started-in-the-adapter",
        "amount": "300.00",
        "refunded_total": "300.00",
        "currency": "INR",
        "gateway_refund_id": "G1",
    }
    assert handle(consumers.PAYMENT_REFUNDED, refunded)["result"] == "completed"
    assert handle(consumers.PAYMENT_REFUNDED, refunded)["reason"] == "refund already completed"
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["paid_total"] == "500.00" and after["status"] == "partially_paid" and after["balance"] == "300.00"
    assert (
        after["payments"][0]["refunded_amount"] == "300.00" and after["payments"][0]["status"] == "partially_refunded"
    )
    too_much = {**refunded, "refund_id": "second", "amount": "600.00"}
    assert handle(consumers.PAYMENT_REFUNDED, too_much)["reason"].startswith("refund of 600.00 exceeds the 500.00")
    unknown = {**refunded, "refund_id": "third", "reference": "NOT-OURS"}
    assert handle(consumers.PAYMENT_REFUNDED, unknown)["reason"] == "no fees-accounts payment with that reference"


def test_a_concession_never_exceeds_what_is_invoiced(client, org):  # F2
    inv = adhoc(client, org, "500.00")
    r = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "waiver", "amount": "800.00", "reason": "x"},
        headers=org.staff,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "exceeds_total"
    first = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "sibling", "amount": "300.00", "reason": "x"},
        headers=org.staff,
    ).json()["id"]
    second = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "scholarship", "percent": 100, "reason": "x"},
        headers=org.staff,
    ).json()["id"]
    assert (
        client.post(f"{BASE}/concessions/{first}/decision", json={"decision": "approved"}, headers=org.manager).json()[
            "approved_amount"
        ]
        == "300.00"
    )
    r = client.post(f"{BASE}/concessions/{second}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 200 and r.json()["approved_amount"] == "200.00"  # capped at what is left of the total
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["concession_total"] == "500.00" and after["status"] == "paid" and after["credit"] == "0.00"
    statement = client.get(f"{BASE}/accounts/{org.ids['student']}/statement", headers=org.staff).json()
    assert statement["closing_balance"] == "0.00"


def test_foreign_currency_is_ignored_and_an_overpayment_shows_as_credit(client, org):  # F3
    inv = adhoc(client, org, "1000.00")
    pay_cash(client, org, inv["id"], "600.00")
    assert handle(consumers.PAYMENT_SUCCEEDED, succeeded(org, inv, "USD1", "1000.00", "USD"))["result"] == "ignored"
    assert handle(consumers.PAYMENT_SUCCEEDED, succeeded(org, inv, "INR1", "1000.00"))["result"] == "applied"
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["paid_total"] == "1600.00" and after["balance"] == "0.00" and after["credit"] == "600.00"
    assert after["status"] == "paid" and len(after["payments"]) == 2
    dues = client.get(f"{BASE}/dues", params={"person_id": org.ids["student"]}, headers=org.exams).json()
    assert dues["balance"] == "0.00"


def test_a_malformed_event_is_ignored_with_its_reason(client, org):  # F5
    result = handle(consumers.PAYMENT_SUCCEEDED, {"organisation_id": org.id, "source_module": "fees-accounts"})
    assert result["result"] == "ignored" and result["reason"].startswith("malformed payload: KeyError")
    bad_date = {**succeeded(org, adhoc(client, org, "10.00"), "BAD1", "10.00"), "completed_at": "not a date"}
    assert handle(consumers.PAYMENT_SUCCEEDED, bad_date)["reason"].startswith("malformed payload: ValueError")
    assert handle(consumers.FINE_RAISED, {"organisation_id": org.id})["result"] == "ignored"


def test_collections_are_net_of_refunds(client, org):  # F6
    inv = adhoc(client, org, "1000.00")
    p = pay_cash(client, org, inv["id"], "1000.00")
    kept = pay_cash(client, org, adhoc(client, org, "250.00")["id"], "250.00")
    r = client.post(
        f"{BASE}/payments/{p['id']}/refunds",
        json={"amount": "1000.00", "reason": "x", "mode": "cash"},
        headers=org.staff,
    )
    assert r.status_code == 202 and r.json()["status"] == "completed"
    report = client.get(f"{BASE}/reports/collections", params={"date": TODAY}, headers=org.staff).json()
    assert report["total"] == "250.00" and report["count"] == 2
    assert report["by_mode"] == [{"mode": "cash", "amount": "250.00", "count": 2}]
    assert {h["amount"] for h in report["by_fee_head"]} == {"250.00", "0.00"}
    target = client.get(
        f"{BASE}/reports/collection-vs-target", params={"academic_year": "2026-27"}, headers=org.staff
    ).json()
    assert target["collected_total"] == "250.00"
    assert [x for x in target["periods"] if x["period"] == "2026-10"][0]["collected"] == "250.00"
    assert kept["status"] == "completed"


def test_ad_hoc_invoices_refuse_inactive_fee_heads(client, org):  # F7
    h = head(client, org, "INACT", "other")
    body = {"code": "INACT", "name": "Inactive", "category": "other", "refundable": False, "active": False}
    assert client.put(f"{BASE}/fee-heads/{h['id']}", json=body, headers=org.staff).status_code == 200
    r = client.post(
        f"{BASE}/invoices",
        json={
            "person_id": org.ids["student"],
            "lines": [{"fee_head_id": h["id"], "amount": "10.00"}],
            "due_date": "2026-11-01",
        },
        headers=org.staff,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_fee_head"
