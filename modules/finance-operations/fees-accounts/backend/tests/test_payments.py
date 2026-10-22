"""Counter payments, receipts, voids, refunds and online payment through the adapter (stories F5-F7, S3)."""

import json

from fees_support import BASE, TODAY, adhoc, invoice, outbox, pay_cash, published


def test_counter_payment_issues_a_receipt(client, org):
    inv = adhoc(client, org, "1000.00")
    p = pay_cash(client, org, inv["id"], "400.00")
    assert (
        p["mode"] == "cash" and p["status"] == "completed" and p["receipt_id"] and p["recorded_by"] == org.ids["staff"]
    )
    receipt = client.get(f"{BASE}/receipts/{p['receipt_id']}", headers=org.staff).json()
    assert receipt["number"].startswith("RCT-") and receipt["amount"] == "400.00" and receipt["status"] == "valid"
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["status"] == "partially_paid" and after["balance"] == "600.00" and after["paid_total"] == "400.00"
    [event] = [e for e in outbox("fees-accounts.payment.received", org.id) if e["payment_id"] == p["id"]]
    assert event["amount"] == "400.00" and event["mode"] == "cash" and event["receipt_id"] == receipt["id"]


def test_paying_the_balance_marks_paid_once(client, org):
    inv = adhoc(client, org, "1000.00", source={"module": "library", "reference": "FINE-1"})
    pay_cash(client, org, inv["id"], "400.00")
    pay_cash(client, org, inv["id"], "600.00")
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["status"] == "paid" and after["balance"] == "0.00" and len(after["payments"]) == 2
    [paid] = [e for e in outbox("fees-accounts.invoice.paid", org.id) if e["invoice_id"] == inv["id"]]
    assert paid["source_module"] == "library" and paid["source_reference"] == "FINE-1"
    r = client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={"amount": "1", "mode": "cash", "paid_on": TODAY},
        headers=org.staff,
    )
    assert r.status_code == 409


def test_payment_above_balance_is_refused(client, org):
    inv = adhoc(client, org, "100.00")
    r = client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={"amount": "100.01", "mode": "cheque", "paid_on": TODAY},
        headers=org.staff,
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "exceeds_balance"


def test_bounced_cheque_is_voided(client, org):
    inv = adhoc(client, org, "500.00")
    p = client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={
            "amount": "500.00",
            "mode": "cheque",
            "paid_on": TODAY,
            "instrument_number": "000123",
            "bank_name": "SBI",
        },
        headers=org.staff,
    ).json()
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()["status"] == "paid"
    v = client.post(f"{BASE}/payments/{p['id']}/void", json={"reason": "cheque bounced"}, headers=org.staff)
    assert v.status_code == 200 and v.json()["status"] == "void"
    assert client.get(f"{BASE}/receipts/{p['receipt_id']}", headers=org.staff).json()["status"] == "cancelled"
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["status"] == "issued" and after["balance"] == "500.00"
    assert (
        client.post(f"{BASE}/payments/{p['id']}/void", json={"reason": "again"}, headers=org.staff).status_code == 409
    )
    assert [e["reason"] for e in outbox("fees-accounts.payment.voided", org.id) if e["payment_id"] == p["id"]] == [
        "cheque bounced"
    ]


def test_offline_refunds_never_above_what_was_paid(client, org):
    inv = adhoc(client, org, "1000.00")
    p = pay_cash(client, org, inv["id"], "1000.00")
    r = client.post(
        f"{BASE}/payments/{p['id']}/refunds", json={"amount": "300", "reason": "overpaid"}, headers=org.staff
    )
    assert r.status_code == 202 and r.json()["status"] == "completed"
    too_much = client.post(
        f"{BASE}/payments/{p['id']}/refunds", json={"amount": "700.01", "reason": "x"}, headers=org.staff
    )
    assert too_much.status_code == 422
    client.post(f"{BASE}/payments/{p['id']}/refunds", json={"amount": "700", "reason": "withdrawal"}, headers=org.staff)
    assert client.get(f"{BASE}/payments/{p['id']}", headers=org.staff).json()["status"] == "refunded"
    assert [e["amount"] for e in outbox("fees-accounts.refund.issued", org.id) if e["payment_id"] == p["id"]] == [
        "300.00",
        "700.00",
    ]
    # a refund returns money; it does not make the fee due again
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()["status"] == "paid"
    assert client.post(f"{BASE}/payments/{p['id']}/void", json={"reason": "x"}, headers=org.staff).status_code == 409


def test_pay_online_asks_the_adapter_for_a_session(client, org, adapter):
    s = published(client, org, allow_part_payment=True)
    inv = invoice(client, org, structure=s)
    adapter.body = {
        "reference": "EOSABC",
        "payment_url": "https://pay.example.com/r/EOSABC",
        "expires_at": "2026-10-22T10:00:00+00:00",
    }
    r = client.post(f"{BASE}/invoices/{inv['id']}/pay", json={"amount": "1000.00"}, headers=org.student)
    assert r.status_code == 201 and r.json()["reference"] == "EOSABC"
    [req] = adapter.requests
    assert str(req.url) == "https://api.example.com/api/v1/payment-sbiepay/payments"
    assert req.headers["Authorization"] == org.student["Authorization"]
    body = json.loads(req.content)
    assert (
        body["purpose"] == "fee" and body["source_module"] == "fees-accounts" and body["source_reference"] == inv["id"]
    )
    assert body["amount"] == "1000.00" and body["return_url"] == "https://college.example.com/fees"


def test_pay_online_rules(client, org, adapter):
    inv = adhoc(client, org, "500.00")
    assert client.post(f"{BASE}/invoices/{inv['id']}/pay", json={}, headers=org.classmate).status_code == 403
    part = client.post(f"{BASE}/invoices/{inv['id']}/pay", json={"amount": "100"}, headers=org.student)
    assert part.status_code == 422 and part.json()["detail"]["code"] == "part_payment_not_allowed"
    adapter.status, adapter.body = (
        409,
        {"reference": "OPEN", "payment_url": "https://pay.example.com/r/OPEN", "expires_at": "x"},
    )
    assert client.post(f"{BASE}/invoices/{inv['id']}/pay", headers=org.student).json()["reference"] == "OPEN"
    adapter.status, adapter.body = 503, {"detail": "no merchant"}
    assert client.post(f"{BASE}/invoices/{inv['id']}/pay", headers=org.student).status_code == 503


def test_pay_online_without_an_adapter_is_503(client, org):
    inv = adhoc(client, org, "500.00")
    r = client.post(
        f"{BASE}/invoices/{inv['id']}/pay", json={"return_url": "https://x.example.com"}, headers=org.student
    )
    assert r.status_code == 503 and r.json()["detail"]["code"] == "payment_not_configured"


def test_online_refund_goes_through_the_adapter(client, org, adapter):
    from eos_core.db import SessionLocal
    from eos_fees_accounts.application import consumers

    inv = adhoc(client, org, "800.00")
    with SessionLocal() as db:
        consumers.handle(
            db,
            "payment-sbiepay.payment.succeeded",
            {
                "organisation_id": org.id,
                "reference": "EOSREF1",
                "source_module": "fees-accounts",
                "source_reference": inv["id"],
                "amount": "800.00",
                "completed_at": "2026-10-22T09:00:00+00:00",
            },
        )
    payment = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()["payments"][0]
    assert (
        client.post(f"{BASE}/payments/{payment['id']}/void", json={"reason": "x"}, headers=org.staff).status_code == 409
    )
    adapter.status, adapter.body = 202, {"id": "ADAPTER-R1", "status": "requested"}
    r = client.post(
        f"{BASE}/payments/{payment['id']}/refunds", json={"amount": "200", "reason": "excess"}, headers=org.staff
    )
    assert r.status_code == 202 and r.json()["status"] == "requested"
    assert str(adapter.requests[-1].url).endswith("/payments/EOSREF1/refunds")
    # the requested refund counts against what is left until the adapter confirms it
    assert (
        client.post(
            f"{BASE}/payments/{payment['id']}/refunds", json={"amount": "600.01", "reason": "x"}, headers=org.staff
        ).status_code
        == 422
    )
    with SessionLocal() as db:
        result = consumers.handle(
            db,
            "payment-sbiepay.payment.refunded",
            {
                "organisation_id": org.id,
                "reference": "EOSREF1",
                "source_module": "fees-accounts",
                "source_reference": inv["id"],
                "refund_id": "ADAPTER-R1",
                "amount": "200.00",
            },
        )
    assert result["result"] == "completed"
    assert client.get(f"{BASE}/payments/{payment['id']}", headers=org.staff).json()["refunded_amount"] == "200.00"


def test_list_payments(client, org):
    inv = adhoc(client, org, "300.00", person="p-list")
    pay_cash(client, org, inv["id"], "100.00")
    items = client.get(f"{BASE}/payments?person_id=p-list&mode=cash&from={TODAY}&to={TODAY}", headers=org.staff).json()[
        "items"
    ]
    assert len(items) == 1 and items[0]["amount"] == "100.00"
    assert client.get(f"{BASE}/payments", headers=org.student).status_code == 403
