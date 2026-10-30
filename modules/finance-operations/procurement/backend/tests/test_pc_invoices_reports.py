"""Vendor invoices matched against the order and accepted receipts, approved by someone other than the recorder and
paid; the purchase-orders-pending report (F7-F10, M4)."""

from datetime import timedelta

from pc_support import BASE, NOW, TODAY, direct_order, issued_order, outbox, receive


def invoice(client, org, po, amount, number=None, who="staff", **fields):
    body = {
        "purchase_order_id": po["id"],
        "invoice_number": number or f"INV-{amount}",
        "invoice_date": TODAY,
        "amount": amount,
        **fields,
    }
    return client.post(f"{BASE}/vendor-invoices", json=body, headers=org.headers[who])


def decide(client, org, inv, decision="approved", who="staff2", **extra):
    return client.post(
        f"{BASE}/vendor-invoices/{inv['id']}/decision", json={"decision": decision, **extra}, headers=org.headers[who]
    )


def test_invoice_match_approval_and_payment(client, org, monkeypatch):
    po = issued_order(client, org)  # 10 x 118.00
    receive(client, org, po, (0, 5, 5))  # 590.00 accepted
    r = invoice(client, org, po, "590.00", "A/1", tax_amount="90.00")
    assert r.status_code == 201, r.text
    inv = r.json()
    assert inv["status"] == "recorded" and inv["vendor_id"] == po["vendor_id"] and inv["tds_deducted"] == "0.00"
    assert inv["match"] == {
        "ordered": "1180.00",
        "accepted_value": "590.00",
        "previously_invoiced": "0.00",
        "within_tolerance": True,
    }
    assert invoice(client, org, po, "1.00", "A/1").json()["detail"]["code"] == "invoice_exists"
    # the recorder never approves
    r = decide(client, org, inv, who="staff")
    assert r.status_code == 403
    assert (
        client.post(
            f"{BASE}/vendor-invoices/{inv['id']}/mark-paid",
            json={"paid_on": TODAY, "payment_reference": "UTR1"},
            headers=org.staff,
        ).status_code
        == 409
    )
    r = decide(client, org, inv)
    assert r.status_code == 200 and r.json()["status"] == "approved" and r.json()["approved_by"] == org.ids["staff2"]
    [approved] = [
        e for e in outbox("procurement.vendor-invoice.approved", org.id) if e["vendor_invoice_id"] == inv["id"]
    ]
    assert approved["amount"] == "590.00" and approved["purchase_order_id"] == po["id"]
    pay = {"paid_on": TODAY, "payment_reference": "UTR123", "tds_deducted": "11.80"}
    assert (
        client.post(f"{BASE}/vendor-invoices/{inv['id']}/mark-paid", json=pay, headers=org.manager).status_code == 403
    )
    r = client.post(
        f"{BASE}/vendor-invoices/{inv['id']}/mark-paid", json={**pay, "paid_on": "2026-12-01"}, headers=org.staff
    )
    assert r.json()["detail"]["code"] == "invalid_date"
    r = client.post(f"{BASE}/vendor-invoices/{inv['id']}/mark-paid", json=pay, headers=org.staff)
    assert r.status_code == 200 and r.json()["status"] == "paid" and r.json()["tds_deducted"] == "11.80"
    [paid] = [e for e in outbox("procurement.vendor-invoice.paid", org.id) if e["vendor_invoice_id"] == inv["id"]]
    assert paid == {
        "organisation_id": org.id,
        "vendor_invoice_id": inv["id"],
        "purchase_order_id": po["id"],
        "vendor_id": po["vendor_id"],
        "line_id": org.line,
        "amount": "590.00",
        "paid_on": TODAY,
    }
    order = client.get(f"{BASE}/purchase-orders/{po['id']}", headers=org.staff).json()
    assert order["invoiced_total"] == "590.00" and order["paid_total"] == "590.00"


def test_a_mismatch_needs_a_note_to_approve(client, org, monkeypatch):
    po = issued_order(client, org)
    receive(client, org, po, (0, 5, 5))  # 590.00 accepted
    inv = invoice(client, org, po, "600.00").json()
    assert inv["match"]["within_tolerance"] is False
    r = decide(client, org, inv)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invoice_mismatch"
    monkeypatch.setenv("PROCUREMENT_INVOICE_MATCH_TOLERANCE_PERCENT", "2")
    assert (
        client.get(f"{BASE}/vendor-invoices/{inv['id']}", headers=org.staff).json()["match"]["within_tolerance"] is True
    )
    monkeypatch.delenv("PROCUREMENT_INVOICE_MATCH_TOLERANCE_PERCENT")
    r = decide(client, org, inv, note="freight agreed by phone")
    assert r.status_code == 200 and r.json()["status"] == "approved"
    # a second invoice counts what was invoiced before
    second = invoice(client, org, po, "10.00", "B/2").json()
    assert second["match"]["previously_invoiced"] == "600.00" and second["match"]["within_tolerance"] is False
    r = decide(client, org, second, "rejected", note="duplicate charge")
    assert r.json()["status"] == "rejected"
    assert decide(client, org, second).status_code == 409
    assert decide(client, org, invoice(client, org, po, "1.00", "C/3").json(), "returned").status_code == 422


def test_invoices_need_an_issued_order(client, org):
    draft = direct_order(client, org)
    r = invoice(client, org, draft, "100.00")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "order_not_issued"
    po = issued_order(client, org)
    assert invoice(client, org, po, "0").status_code == 422
    assert invoice(client, org, po, "10.00", tax_amount="11.00").json()["detail"]["code"] == "invalid_amount"
    assert invoice(client, org, po, "10.00", invoice_date="2026-12-31").json()["detail"]["code"] == "invalid_date"
    assert invoice(client, org, po, "10.00", who="faculty").status_code == 403
    assert invoice(client, org, po, "10.00", who="manager").status_code == 403
    listed = client.get(f"{BASE}/vendor-invoices?vendor_id={po['vendor_id']}", headers=org.staff).json()["items"]
    assert listed == []


def test_purchase_orders_pending_report(client, org, monkeypatch):
    awaiting = direct_order(client, org)
    client.post(f"{BASE}/purchase-orders/{awaiting['id']}/submit", headers=org.staff)
    on_time = issued_order(client, org)
    late = issued_order(client, org, delivery_by=TODAY)  # due today; overdue from tomorrow
    received = issued_order(client, org)
    receive(client, org, received, (0, 10, 10))
    inv = invoice(client, org, received, "1180.00").json()
    decide(client, org, inv)
    from eos_procurement.application import service

    monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(days=1))
    report = client.get(f"{BASE}/reports/purchase-orders-pending", headers=org.staff).json()
    assert report["awaiting_approval"] == {"count": 1, "value": "1180.00"}
    assert report["awaiting_delivery"] == {"count": 2, "value": "2360.00"}
    assert report["overdue_delivery"] == {"count": 1, "value": "1180.00"}
    assert report["invoices_awaiting_payment"] == {"count": 1, "value": "1180.00"}
    assert {x["id"] for x in report["oldest"]} == {awaiting["id"], on_time["id"], late["id"]}
    assert all(x["since"] == TODAY and x["vendor_name"] for x in report["oldest"])
    late_row = client.get(f"{BASE}/purchase-orders/{late['id']}", headers=org.staff).json()
    assert late_row["overdue"] is True
    assert client.get(f"{BASE}/reports/purchase-orders-pending", headers=org.admin).status_code == 200
    assert client.get(f"{BASE}/reports/purchase-orders-pending", headers=org.faculty).status_code == 403


def test_report_of_an_empty_organisation(client, org):
    report = client.get(f"{BASE}/reports/purchase-orders-pending", headers=org.manager).json()
    zero = {"count": 0, "value": "0.00"}
    assert report == {
        "awaiting_approval": zero,
        "awaiting_delivery": zero,
        "overdue_delivery": zero,
        "invoices_awaiting_payment": zero,
        "oldest": [],
    }
