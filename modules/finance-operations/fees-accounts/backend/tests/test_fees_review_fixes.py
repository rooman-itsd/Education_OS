"""Regression tests for the defects an independent review found; each failed before its fix."""

from decimal import Decimal

import pytest
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_fees_accounts.application import consumers
from eos_fees_accounts.domain import rules
from fees_support import BASE, adhoc, head, pay_cash, published


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
