"""The decisions recorded on #335: the order total is checked against its line before an order is issued; business dates
follow Asia/Kolkata (IST); an expired quote is not awarded."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_procurement.infrastructure.models import AuditEntry
from pc_support import BASE, BUDGET_URL, LATER, NOW, direct_order, issued_order, item, outbox, receive, vendor
from sqlalchemy import select

# 18:30 UTC is midnight in India (UTC+05:30).
IST_2359_ON_28 = datetime(2026, 10, 28, 18, 29, tzinfo=UTC)
IST_0000_ON_29 = datetime(2026, 10, 28, 18, 30, tzinfo=UTC)


def _at(monkeypatch, moment):
    from eos_procurement.application import service

    monkeypatch.setattr(service, "clock", lambda: moment)


def _submitted(client, org, **kwargs):
    po = direct_order(client, org, **kwargs)  # 10 x 100.00 + 18% = 1180.00
    assert client.post(f"{BASE}/purchase-orders/{po['id']}/submit", headers=org.staff).status_code == 200
    return po


def _approve(client, org, po, who="manager"):
    return client.post(
        f"{BASE}/purchase-orders/{po['id']}/decision", json={"decision": "approved"}, headers=org.headers[who]
    )


# ---------------------------------------------------------------- 1. the order total is covered by its line


def test_an_order_the_line_cannot_cover_is_not_issued_and_nothing_changes(client, org, budget):
    po = _submitted(client, org)
    budget.available[org.line] = Decimal("1179.99")
    r = _approve(client, org, po)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "insufficient_budget"
    assert "1179.99" in r.json()["detail"]["message"] and "1180.00" in r.json()["detail"]["message"]
    after = client.get(f"{BASE}/purchase-orders/{po['id']}", headers=org.staff).json()
    assert after["status"] == "submitted" and after["approved_by"] is None and after["issued_at"] is None
    assert not [e for e in outbox("procurement.purchase-order.issued", org.id) if e["purchase_order_id"] == po["id"]]
    [indent_id] = po["indent_ids"]
    assert client.get(f"{BASE}/indents/{indent_id}", headers=org.manager).json()["status"] == "approved"
    with SessionLocal() as db, platform_scope():
        actions = list(db.scalars(select(AuditEntry.action).where(AuditEntry.entity_id == po["id"])))
    assert "purchase_order.issued" not in actions
    budget.available[org.line] = Decimal("1180.00")  # exactly the total is enough
    assert _approve(client, org, po).json()["status"] == "issued"


def test_the_check_uses_the_order_total_and_the_approvers_token(client, org, budget):
    po = _submitted(client, org)
    calls = len(budget.requests)
    assert _approve(client, org, po).status_code == 200
    availability, listing = budget.requests[calls:]
    assert str(availability.url).startswith(f"{BUDGET_URL}/availability")
    assert availability.url.params["amount"] == "1180.00" and availability.url.params["line_id"] == org.line
    assert str(listing.url).startswith(f"{BUDGET_URL}/expenditures") and listing.url.params["kind"] == "commitment"
    for req in (availability, listing):
        assert req.headers["authorization"] == f"Bearer {org.token('manager')}"
    # returning an order checks nothing
    other = _submitted(client, org)
    calls = len(budget.requests)
    r = client.post(
        f"{BASE}/purchase-orders/{other['id']}/decision", json={"decision": "returned"}, headers=org.manager
    )
    assert r.json()["status"] == "returned" and len(budget.requests) == calls


def test_orders_budget_grants_has_not_recorded_yet_are_counted_once(client, org, budget):
    """The line has 2500. Until budget-grants receives the issued events, it still reports 2500 available."""
    budget.available[org.line] = Decimal("2500")
    a = issued_order(client, org)  # 1180, not recorded by budget-grants yet
    b = _submitted(client, org)
    assert _approve(client, org, b).status_code == 200  # 2500 - 1180 pending = 1320 left
    c = _submitted(client, org)
    r = _approve(client, org, c)  # 2500 - 2360 pending = 140 left
    assert r.status_code == 422 and "2360.00 of it held" in r.json()["detail"]["message"]
    # once budget-grants has recorded both commitments, it reports 140 and nothing is subtracted twice
    budget.recorded |= {a["id"], b["id"]}
    budget.available[org.line] = Decimal("140")
    r = _approve(client, org, c)
    assert r.status_code == 422 and "held" not in r.json()["detail"]["message"]
    budget.available[org.line] = Decimal("1180")  # say, after a reappropriation
    budget.page_size = 1  # the listing is read across pages
    assert _approve(client, org, c).json()["status"] == "issued"


def test_cancelled_orders_and_other_lines_hold_nothing(client, org, budget):
    from eos_core.db import new_id
    from pc_support import approved_indent

    budget.available[org.line] = Decimal("1180")
    cancelled = issued_order(client, org)  # on this line, then cancelled with nothing received
    client.post(f"{BASE}/purchase-orders/{cancelled['id']}/cancel", json={"reason": "not needed"}, headers=org.manager)
    other_line = new_id()
    elsewhere = approved_indent(client, org, line=other_line)
    body = {
        "vendor_id": vendor(client, org)["id"],
        "indent_ids": [elsewhere["id"]],
        "items": [item(10, "100.00", 18)],
        "delivery_by": "2026-11-30",
    }
    on_other_line = client.post(f"{BASE}/purchase-orders", json=body, headers=org.staff).json()
    client.post(f"{BASE}/purchase-orders/{on_other_line['id']}/submit", headers=org.staff)
    assert _approve(client, org, on_other_line).json()["status"] == "issued"  # issued, not recorded, other line
    po = _submitted(client, org)
    assert _approve(client, org, po).json()["status"] == "issued"  # neither of them holds this line's 1180


def test_budget_grants_unavailable_leaves_the_order_submitted(client, org, budget, monkeypatch):
    po = _submitted(client, org)
    budget.expenditures_status = 403  # the approver lacks budget-grants:budget:read
    r = _approve(client, org, po)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "budget_check_unavailable"
    budget.expenditures_status, budget.missing = None, {org.line}
    r = _approve(client, org, po)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "insufficient_budget"
    budget.missing, budget.down = set(), True
    assert _approve(client, org, po).status_code == 503
    budget.down = False
    monkeypatch.delenv("PROCUREMENT_BUDGET_GRANTS_URL")
    assert _approve(client, org, po).status_code == 503
    assert client.get(f"{BASE}/purchase-orders/{po['id']}", headers=org.staff).json()["status"] == "submitted"


# ---------------------------------------------------------------- 2. business dates follow Asia/Kolkata


def test_a_receipt_dated_today_in_india_is_accepted_after_ist_midnight(client, org, monkeypatch):
    po = issued_order(client, org)
    _at(monkeypatch, IST_2359_ON_28)
    r = receive(client, org, po, (0, 1, 1), received_on="2026-10-29")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"  # still the 28th in India
    _at(monkeypatch, IST_0000_ON_29)  # the 28th in UTC, already the 29th in India
    assert receive(client, org, po, (0, 1, 1), received_on="2026-10-29").status_code == 201
    assert receive(client, org, po, (0, 1, 1), received_on="2026-10-30").status_code == 422


def test_invoice_and_payment_dates_follow_india(client, org, monkeypatch):
    po = issued_order(client, org)
    receive(client, org, po, (0, 10, 10))
    _at(monkeypatch, IST_0000_ON_29)
    body = {"purchase_order_id": po["id"], "invoice_number": "IST/1", "invoice_date": "2026-10-29", "amount": "1180.00"}
    inv = client.post(f"{BASE}/vendor-invoices", json=body, headers=org.staff)
    assert inv.status_code == 201
    client.post(
        f"{BASE}/vendor-invoices/{inv.json()['id']}/decision", json={"decision": "approved"}, headers=org.staff2
    )
    pay = {"paid_on": "2026-10-29", "payment_reference": "UTR-IST"}
    r = client.post(f"{BASE}/vendor-invoices/{inv.json()['id']}/mark-paid", json=pay, headers=org.staff)
    assert r.status_code == 200 and r.json()["paid_on"] == "2026-10-29"
    late = {**body, "invoice_number": "IST/2", "invoice_date": "2026-10-30"}
    assert client.post(f"{BASE}/vendor-invoices", json=late, headers=org.staff).status_code == 422


def test_overdue_starts_at_ist_midnight_after_the_delivery_date(client, org, monkeypatch):
    po = issued_order(client, org, delivery_by="2026-10-28")
    _at(monkeypatch, IST_2359_ON_28)
    assert client.get(f"{BASE}/purchase-orders/{po['id']}", headers=org.staff).json()["overdue"] is False
    _at(monkeypatch, IST_0000_ON_29)
    assert client.get(f"{BASE}/purchase-orders/{po['id']}", headers=org.staff).json()["overdue"] is True
    report = client.get(f"{BASE}/reports/purchase-orders-pending", headers=org.staff).json()
    assert report["overdue_delivery"]["count"] >= 1


def test_the_report_dates_an_order_in_india(client, org, monkeypatch):
    _at(monkeypatch, IST_0000_ON_29)
    po = _submitted(client, org)  # submitted at 18:30 UTC on the 28th, 00:00 IST on the 29th
    oldest = client.get(f"{BASE}/reports/purchase-orders-pending", headers=org.staff).json()["oldest"]
    assert {x["id"]: x["since"] for x in oldest}[po["id"]] == "2026-10-29"


# ---------------------------------------------------------------- 3. an expired quote is not awarded


def _closed_tender_with_quotes(client, org, monkeypatch, *quotes):
    from pc_support import approved_indent

    ind = approved_indent(client, org, "60000.00")
    body = {
        "title": "t",
        "indent_ids": [ind["id"]],
        "method": "quotation",
        "category": "lab equipment",
        "closes_at": LATER,
    }
    t = client.post(f"{BASE}/tenders", json=body, headers=org.staff).json()
    vendors = [vendor(client, org) for _ in quotes]
    assert client.post(f"{BASE}/tenders/{t['id']}/publish", headers=org.staff).status_code == 200
    ids = []
    for v, (total, valid_until) in zip(vendors, quotes, strict=True):
        q = {"vendor_id": v["id"], "items": [item(1, total)], "total": total, "valid_until": valid_until}
        tender = client.post(f"{BASE}/tenders/{t['id']}/quotes", json=q, headers=org.staff).json()
        ids.append(next(x["id"] for x in tender["quotes"] if x["vendor_id"] == v["id"]))
    return t, ids


def _award(client, org, t, quote_id, **extra):
    return client.post(f"{BASE}/tenders/{t['id']}/award", json={"quote_id": quote_id, **extra}, headers=org.staff)


def test_a_quote_is_valid_through_its_valid_until_date_in_india(client, org, monkeypatch):
    t, [q] = _closed_tender_with_quotes(client, org, monkeypatch, ("50000.00", "2026-11-05"))
    _at(monkeypatch, datetime(2026, 11, 5, 18, 29, tzinfo=UTC))  # 23:59 IST on its last valid day, after closing
    assert _award(client, org, t, q).status_code == 200


def test_an_expired_quote_is_409(client, org, monkeypatch):
    t, [q] = _closed_tender_with_quotes(client, org, monkeypatch, ("50000.00", "2026-11-05"))
    _at(
        monkeypatch, datetime(2026, 11, 5, 18, 30, tzinfo=UTC)
    )  # 00:00 IST on 6 November: expired, though still the 5th in UTC
    r = _award(client, org, t, q)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "quote_expired"
    assert client.get(f"{BASE}/tenders/{t['id']}", headers=org.staff).json()["status"] == "closed"


def test_an_expired_lower_quote_does_not_demand_a_justification(client, org, monkeypatch):
    t, [cheap, valid] = _closed_tender_with_quotes(
        client, org, monkeypatch, ("40000.00", "2026-11-01"), ("45000.00", "2026-12-31")
    )
    _at(monkeypatch, NOW + timedelta(days=8))  # 5 November: the cheaper quote expired on the 1st
    r = _award(client, org, t, valid)
    assert r.status_code == 200 and r.json()["total"] == "45000.00"


def test_the_line_is_locked_before_the_budget_is_checked(client, org, monkeypatch):
    """Approvals on one line are serialised. On Postgres the lock is pg_advisory_xact_lock; two approvals racing for one
    balance were verified there in the review (one issued, one 422; without the lock both were issued)."""
    from eos_procurement.application import service

    po = _submitted(client, org)
    calls = []
    real_lock, real_check = service._lock_line, service._check_order_budget
    monkeypatch.setattr(
        service,
        "_lock_line",
        lambda db, org_id, line: (calls.append(("lock", org_id, line)), real_lock(db, org_id, line)),
    )
    monkeypatch.setattr(
        service, "_check_order_budget", lambda db, actor, o: (calls.append(("check", o.id)), real_check(db, actor, o))
    )
    assert _approve(client, org, po).status_code == 200
    assert calls == [("lock", org.id, org.line), ("check", po["id"])]
