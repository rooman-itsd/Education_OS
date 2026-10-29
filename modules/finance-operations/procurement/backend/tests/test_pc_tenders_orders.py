"""Quotations and tenders, purchase orders with approval by someone other than the preparer, goods receipts and
cancellation (F4-F6, M2, M3, S1)."""

from datetime import timedelta

from eos_core.db import new_id
from eos_core.security import create_token
from pc_support import (
    BASE,
    LATER,
    NOW,
    TODAY,
    approved_indent,
    auth,
    direct_order,
    issued_order,
    item,
    outbox,
    receive,
    vendor,
)


def tender(client, org, indents, method="quotation", **fields):
    body = {
        "title": "Spectrophotometer",
        "indent_ids": [i["id"] for i in indents],
        "method": method,
        "category": "lab equipment",
        "closes_at": LATER,
        **fields,
    }
    return client.post(f"{BASE}/tenders", json=body, headers=org.staff)


def quote(client, org, t, v, total, priced=True):
    items = [item(2, f"{int(total) // 2}.00")] if priced else []
    return client.post(
        f"{BASE}/tenders/{t['id']}/quotes",
        json={"vendor_id": v["id"], "items": items, "total": total, "delivery_days": 10},
        headers=org.staff,
    )


def close(monkeypatch):
    """Move the clock past the closing date."""
    from eos_procurement.application import service

    monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(days=8))


def test_quotation_from_request_to_award(client, org, monkeypatch):
    i1, i2 = approved_indent(client, org, "60000.00"), approved_indent(client, org, "30000.00")
    low, high, other = vendor(client, org), vendor(client, org), vendor(client, org, categories=["IT"])
    r = tender(client, org, [i1, i2])
    assert r.status_code == 201, r.text
    t = r.json()
    assert t["status"] == "draft" and t["number"].startswith("RFQ-") and t["line_id"] == org.line
    assert sorted(t["indent_ids"]) == sorted([i1["id"], i2["id"]])
    # an indent belongs to one open tender at a time
    assert tender(client, org, [i1]).json()["detail"]["code"] == "indent_in_use"
    assert quote(client, org, t, low, "1000").status_code == 409  # not published yet
    r = client.post(f"{BASE}/tenders/{t['id']}/publish", headers=org.staff)
    assert r.status_code == 200 and r.json()["status"] == "published"
    [published] = [e for e in outbox("procurement.tender.published", org.id) if e["tender_id"] == t["id"]]
    assert published["method"] == "quotation" and published["category"] == "lab equipment"
    assert quote(client, org, t, high, "90000").status_code == 201
    r = quote(client, org, t, low, "80000")
    assert r.status_code == 201
    assert [q["vendor_id"] for q in r.json()["quotes"]] == [low["id"], high["id"]]  # lowest first
    assert [q["rank"] for q in r.json()["quotes"]] == [1, 2]
    assert quote(client, org, t, low, "70000").json()["detail"]["code"] == "quote_exists"
    assert quote(client, org, t, other, "60000").json()["detail"]["code"] == "vendor_not_invited"
    award = {"quote_id": r.json()["quotes"][1]["id"]}
    assert (
        client.post(f"{BASE}/tenders/{t['id']}/award", json=award, headers=org.staff).status_code == 409
    )  # still open
    close(monkeypatch)
    assert client.get(f"{BASE}/tenders/{t['id']}", headers=org.staff).json()["status"] == "closed"
    assert [x["id"] for x in client.get(f"{BASE}/tenders?status=closed", headers=org.staff).json()] == [t["id"]]
    assert quote(client, org, t, other, "1").json()["detail"]["code"] == "tender_closed"
    r = client.post(f"{BASE}/tenders/{t['id']}/award", json=award, headers=org.staff)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "justification_required"
    r = client.post(
        f"{BASE}/tenders/{t['id']}/award", json={**award, "justification": "faster service"}, headers=org.staff
    )
    assert r.status_code == 200, r.text
    po = r.json()
    assert po["status"] == "draft" and po["vendor_id"] == high["id"] and po["tender_id"] == t["id"]
    assert (
        po["total"] == "90000.00" and po["line_id"] == org.line and sorted(po["indent_ids"]) == sorted(t["indent_ids"])
    )
    t = client.get(f"{BASE}/tenders/{t['id']}", headers=org.staff).json()
    assert t["status"] == "awarded" and t["award_justification"] == "faster service"
    [awarded] = [e for e in outbox("procurement.tender.awarded", org.id) if e["tender_id"] == t["id"]]
    assert awarded["vendor_id"] == high["id"] and awarded["total"] == "90000.00"


def test_tender_rules(client, org):
    quoted = approved_indent(client, org, "600000.00")  # above the quotation limit: a tender
    r = tender(client, org, [quoted], method="quotation")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "method_too_loose"
    direct1, direct2 = approved_indent(client, org, "30000.00"), approved_indent(client, org, "30000.00")
    r = tender(client, org, [direct1, direct2], method="quotation")  # together 60000: quotations
    assert r.status_code == 201
    other_line = approved_indent(client, org, "100.00", line=new_id())
    r = tender(client, org, [approved_indent(client, org), other_line])
    assert r.json()["detail"]["code"] == "lines_differ"
    draft = client.post(
        f"{BASE}/indents",
        json={"title": "x", "line_id": org.line, "items": [item()], "estimated_cost": "10"},
        headers=org.faculty,
    ).json()
    assert tender(client, org, [draft]).json()["detail"]["code"] == "indent_not_approved"
    assert tender(client, org, [approved_indent(client, org)], category="", invited_vendor_ids=[]).status_code == 422
    pending = vendor(client, org, approved=False)
    r = tender(client, org, [approved_indent(client, org)], invited_vendor_ids=[pending["id"]])
    assert r.json()["detail"]["code"] == "vendor_not_approved"
    r = tender(client, org, [approved_indent(client, org)], closes_at=(NOW - timedelta(hours=1)).isoformat())
    assert r.json()["detail"]["code"] == "invalid_closes_at"
    t = tender(client, org, [approved_indent(client, org)], category="furniture").json()
    r = client.post(f"{BASE}/tenders/{t['id']}/publish", headers=org.staff)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "no_vendors"
    assert client.get(f"{BASE}/tenders", headers=org.manager).status_code == 403


def test_direct_order_needs_a_direct_indent_and_an_approved_vendor(client, org):
    v = vendor(client, org)
    quoted = approved_indent(client, org, "60000.00")
    body = {"vendor_id": v["id"], "indent_ids": [quoted["id"]], "items": [item()], "delivery_by": "2026-11-30"}
    r = client.post(f"{BASE}/purchase-orders", json=body, headers=org.staff)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "tender_required"
    i = approved_indent(client, org)
    body["indent_ids"] = [i["id"]]
    pending = vendor(client, org, approved=False)
    r = client.post(f"{BASE}/purchase-orders", json={**body, "vendor_id": pending["id"]}, headers=org.staff)
    assert r.json()["detail"]["code"] == "vendor_not_approved"
    r = client.post(f"{BASE}/purchase-orders", json={**body, "items": [item(unit_price=None)]}, headers=org.staff)
    assert r.json()["detail"]["code"] == "price_required"
    r = client.post(f"{BASE}/purchase-orders", json=body, headers=org.staff)
    assert r.status_code == 201
    po = r.json()
    assert po["number"].startswith("PO-") and po["subtotal"] == "1000.00" and po["total"] == "1000.00"
    assert po["prepared_by"] == org.ids["staff"] and po["status"] == "draft" and po["vendor_name"] == v["name"]
    assert (
        client.post(f"{BASE}/purchase-orders", json=body, headers=org.staff).json()["detail"]["code"] == "indent_in_use"
    )
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.faculty).json()["purchase_order_ids"] == [po["id"]]


def test_the_preparer_never_approves_an_order(client, org):
    po = direct_order(client, org)
    url = f"{BASE}/purchase-orders/{po['id']}"
    assert client.post(f"{url}/decision", json={"decision": "approved"}, headers=org.manager).status_code == 409
    assert client.post(f"{url}/submit", headers=org.staff).json()["status"] == "submitted"
    both = client.post(f"{url}/decision", json={"decision": "approved"}, headers=org.staff)
    assert both.status_code == 403  # finance staff have no approve permission
    r = client.post(f"{url}/decision", json={"decision": "rejected"}, headers=org.manager)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_decision"
    r = client.post(f"{url}/decision", json={"decision": "returned", "note": "wrong address"}, headers=org.manager)
    assert r.json()["status"] == "returned"
    # whoever edits or submits prepares the order: here the manager edits, so the manager cannot approve
    body = {
        "vendor_id": po["vendor_id"],
        "indent_ids": po["indent_ids"],
        "items": [item(5, "100.00")],
        "delivery_by": "2026-12-01",
    }
    dual = auth(create_token(user_id=org.ids["manager"], organisation_id=org.id, roles=["finance-staff", "management"]))
    r = client.put(url, json=body, headers=dual)
    assert r.status_code == 200 and r.json()["prepared_by"] == org.ids["manager"] and r.json()["total"] == "500.00"
    assert client.post(f"{url}/submit", headers=dual).status_code == 200
    r = client.post(f"{url}/decision", json={"decision": "approved"}, headers=dual)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "forbidden"
    r = client.post(f"{url}/decision", json={"decision": "approved"}, headers=org.manager2)
    assert r.status_code == 200 and r.json()["status"] == "issued" and r.json()["approved_by"] == org.ids["manager2"]


def test_issuing_publishes_the_commitment_for_budget_grants(client, org):
    po = issued_order(client, org)
    assert po["status"] == "issued" and po["issued_at"] and po["total"] == "1180.00"
    [event] = [e for e in outbox("procurement.purchase-order.issued", org.id) if e["purchase_order_id"] == po["id"]]
    assert event == {
        "organisation_id": org.id,
        "purchase_order_id": po["id"],
        "number": po["number"],
        "vendor_id": po["vendor_id"],
        "line_id": org.line,
        "total": "1180.00",
        "delivery_by": po["delivery_by"],
        "document_id": "",
    }
    [indent_id] = po["indent_ids"]
    assert client.get(f"{BASE}/indents/{indent_id}", headers=org.manager).json()["status"] == "ordered"
    # a vendor blacklisted after drafting cannot be issued an order
    po2 = direct_order(client, org)
    client.post(f"{BASE}/purchase-orders/{po2['id']}/submit", headers=org.staff)
    client.post(
        f"{BASE}/vendors/{po2['vendor_id']}/status",
        json={"status": "blacklisted", "reason": "fraud"},
        headers=org.staff,
    )
    r = client.post(f"{BASE}/purchase-orders/{po2['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "vendor_not_approved"


def test_goods_receipts_part_and_full(client, org):
    po = issued_order(client, org, items=[item(10, "100.00"), item(2, "500.00", description="Hot plate")])
    assert receive(client, org, po, (0, 11, 11)).json()["detail"]["code"] == "quantity_exceeds_outstanding"
    assert receive(client, org, po, (0, 4, 5)).status_code == 422  # accepted above received
    assert receive(client, org, po, (2, 1, 1)).json()["detail"]["code"] == "invalid_item"
    assert receive(client, org, po, (0, 1, 1), received_on="2026-12-31").json()["detail"]["code"] == "invalid_date"
    r = receive(client, org, po, (0, 6, 4))  # two rejected, with a reason
    assert r.status_code == 201, r.text
    gr = r.json()
    assert gr["number"].startswith("GRN-") and gr["items"][0] == {
        "item_index": 0,
        "received": 6,
        "accepted": 4,
        "rejection_reason": "broken",
    }
    assert client.get(f"{BASE}/purchase-orders/{po['id']}", headers=org.staff).json()["status"] == "partially_received"
    [event] = [e for e in outbox("procurement.goods-receipt.recorded", org.id) if e["goods_receipt_id"] == gr["id"]]
    assert event["vendor_id"] == po["vendor_id"] and event["received_on"] == TODAY
    assert event["items"] == [
        {"item_index": 0, "description": "Beaker 250 ml", "unit": "nos", "received": 6, "accepted": 4}
    ]
    # the rejected two can be delivered again: 6 remain outstanding on item 0
    assert receive(client, org, po, (0, 7, 7)).status_code == 422
    assert receive(client, org, po, (0, 6, 6), (1, 2, 2)).status_code == 201
    assert client.get(f"{BASE}/purchase-orders/{po['id']}", headers=org.facility).json()["status"] == "received"
    [indent_id] = po["indent_ids"]
    assert client.get(f"{BASE}/indents/{indent_id}", headers=org.manager).json()["status"] == "closed"
    assert receive(client, org, po, (0, 1, 1)).status_code == 409
    receipts = client.get(f"{BASE}/purchase-orders/{po['id']}/goods-receipts", headers=org.research).json()
    assert len(receipts) == 2
    r = client.post(
        f"{BASE}/purchase-orders/{po['id']}/goods-receipts",
        json={"received_on": TODAY, "items": [{"item_index": 0, "received": 1, "accepted": 1}]},
        headers=org.staff,
    )
    assert r.status_code == 403  # finance staff do not record receipts


def test_cancel_releases_what_was_not_delivered(client, org):
    po = issued_order(client, org)  # 10 x 100.00 + 18% = 1180.00
    url = f"{BASE}/purchase-orders/{po['id']}/cancel"
    assert client.post(url, json={"reason": "budget cut"}, headers=org.staff).status_code == 403
    r = client.post(url, json={"reason": "budget cut"}, headers=org.manager)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    [event] = [e for e in outbox("procurement.purchase-order.cancelled", org.id) if e["purchase_order_id"] == po["id"]]
    assert event == {
        "organisation_id": org.id,
        "purchase_order_id": po["id"],
        "line_id": org.line,
        "released_amount": "1180.00",
        "reason": "budget cut",
    }
    [indent_id] = po["indent_ids"]
    assert client.get(f"{BASE}/indents/{indent_id}", headers=org.manager).json()["status"] == "approved"
    assert client.post(url, json={"reason": "again"}, headers=org.manager).status_code == 409
    # the indent can be ordered again once its order is cancelled
    v = vendor(client, org)
    body = {"vendor_id": v["id"], "indent_ids": [indent_id], "items": [item()], "delivery_by": "2026-11-30"}
    assert client.post(f"{BASE}/purchase-orders", json=body, headers=org.staff).status_code == 201
    # a part-received order closes its remainder
    po2 = issued_order(client, org)
    receive(client, org, po2, (0, 4, 4))
    r = client.post(
        f"{BASE}/purchase-orders/{po2['id']}/cancel", json={"reason": "rest not needed"}, headers=org.manager
    )
    assert r.json()["status"] == "closed"
    [event] = [e for e in outbox("procurement.purchase-order.cancelled", org.id) if e["purchase_order_id"] == po2["id"]]
    assert event["released_amount"] == "708.00"  # 6 x 118.00 not delivered
    assert client.get(f"{BASE}/indents/{po2['indent_ids'][0]}", headers=org.manager).json()["status"] == "closed"
