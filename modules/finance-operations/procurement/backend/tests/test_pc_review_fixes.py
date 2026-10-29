"""Regression tests for the defects an independent review of the backend found (#335)."""

from datetime import timedelta

import httpx
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_procurement.infrastructure.models import AuditEntry
from pc_support import BASE, LATER, NOW, TODAY, approved_indent, issued_order, item, receive, vendor
from sqlalchemy import select


def _indent(client, org, cost="1", **fields):
    body = {"title": "a", "line_id": org.line, "items": [item()], "estimated_cost": cost, **fields}
    return client.post(f"{BASE}/indents", json=body, headers=org.faculty)


def _order(client, org, indents, items, **fields):
    v = vendor(client, org)
    body = {"vendor_id": v["id"], "indent_ids": [i["id"] for i in indents], "items": items, "delivery_by": "2026-11-30"}
    return client.post(f"{BASE}/purchase-orders", json={**body, **fields}, headers=org.staff)


def _tender(client, org, indent, closes_at=LATER):
    body = {
        "title": "t",
        "indent_ids": [indent["id"]],
        "method": "quotation",
        "category": "lab equipment",
        "closes_at": closes_at,
    }
    return client.post(f"{BASE}/tenders", json=body, headers=org.staff)


def _later(monkeypatch, days=8):
    from eos_procurement.application import service

    monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(days=days))


def test_a_number_taken_concurrently_is_409_not_500(client, org, monkeypatch):
    """The database refuses the duplicate at the flush inside the audit record; that must still answer 409."""
    from eos_procurement.application import service

    real = service._next_number
    taken = _indent(client, org).json()["number"]
    monkeypatch.setattr(service, "_next_number", lambda db, model, prefix: taken)
    r = _indent(client, org)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "number_taken"
    monkeypatch.setattr(service, "_next_number", real)
    first, second = approved_indent(client, org), approved_indent(client, org)
    po_number = _order(client, org, [first], [item()]).json()["number"]
    monkeypatch.setattr(service, "_next_number", lambda db, model, prefix: po_number)
    r = _order(client, org, [second], [item()])
    assert r.status_code == 409 and r.json()["detail"]["code"] == "number_taken"


def test_direct_purchases_cannot_be_split_or_exceed_the_direct_limit(client, org):
    a, b = approved_indent(client, org, "40000.00"), approved_indent(client, org, "40000.00")
    assert a["purchase_method"] == b["purchase_method"] == "direct"
    r = _order(client, org, [a, b], [item(2, "40000.00")])  # together 80000, above the 50000 direct limit
    assert r.status_code == 422 and r.json()["detail"]["code"] == "tender_required"
    small = approved_indent(client, org, "1000.00")
    r = _order(client, org, [small], [item(1, "900000.00")])  # the order itself far above the estimate and the limit
    assert r.status_code == 422 and r.json()["detail"]["code"] == "tender_required"
    po = _order(client, org, [small], [item(1, "50000.00")]).json()  # exactly the limit is still direct
    assert po["total"] == "50000.00"
    edit = {
        "vendor_id": po["vendor_id"],
        "indent_ids": [small["id"]],
        "items": [item(1, "60000.00")],
        "delivery_by": "2026-11-30",
    }
    r = client.put(f"{BASE}/purchase-orders/{po['id']}", json=edit, headers=org.staff)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "tender_required"


def test_the_indent_rows_are_locked_while_checked(client, org, monkeypatch):
    """Two requests for one indent take turns (verified with concurrent requests on Postgres in the review)."""
    from eos_procurement.application import service

    locked = []
    real = service._get

    def spy(db, model, row_id, what, *, lock=False):
        if model is service.Indent:
            locked.append(lock)
        return real(db, model, row_id, what, lock=lock)

    i = approved_indent(client, org)
    monkeypatch.setattr(service, "_get", spy)
    assert _order(client, org, [i], [item()]).status_code == 201
    assert locked == [True]


def test_a_tender_that_can_no_longer_be_awarded_lets_its_indents_go(client, org, monkeypatch):
    unpublished, quiet, quoted = (approved_indent(client, org, "60000.00") for _ in range(3))
    v = vendor(client, org)
    _tender(client, org, unpublished)  # a draft never published
    t_quiet = _tender(client, org, quiet).json()
    client.post(f"{BASE}/tenders/{t_quiet['id']}/publish", headers=org.staff)  # no quote will come
    t_quoted = _tender(client, org, quoted).json()
    client.post(f"{BASE}/tenders/{t_quoted['id']}/publish", headers=org.staff)
    quote = {"vendor_id": v["id"], "items": [item(1, "55000.00")], "total": "55000"}
    assert client.post(f"{BASE}/tenders/{t_quoted['id']}/quotes", json=quote, headers=org.staff).status_code == 201
    assert _tender(client, org, quiet).json()["detail"]["code"] == "indent_in_use"  # still open
    _later(monkeypatch)
    again = (NOW + timedelta(days=20)).isoformat()
    assert _tender(client, org, unpublished, again).status_code == 201
    assert _tender(client, org, quiet, again).status_code == 201
    r = _tender(client, org, quoted, again)  # closed with a quote: it can still be awarded
    assert r.status_code == 409 and r.json()["detail"]["code"] == "indent_in_use"


def test_long_ids_are_refused_before_the_database(client, org):
    r = _indent(client, org, department_id="d" * 60)
    assert r.status_code == 422
    po = issued_order(client, org)
    body = {
        "purchase_order_id": po["id"],
        "invoice_number": "L1",
        "invoice_date": "2026-10-28",
        "amount": "1.00",
        "document_id": "x" * 150,
    }
    assert client.post(f"{BASE}/vendor-invoices", json=body, headers=org.staff).status_code == 422


def test_blacklisting_is_final(client, org):
    v = vendor(client, org)
    url = f"{BASE}/vendors/{v['id']}/status"
    assert (
        client.post(url, json={"status": "blacklisted", "reason": "fake invoices"}, headers=org.staff).status_code
        == 200
    )
    for status in ("approved", "suspended"):
        r = client.post(url, json={"status": status, "reason": "reconsidered"}, headers=org.staff)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "vendor_blacklisted"


def test_an_unreadable_budget_answer_decides_nothing(client, org, monkeypatch):
    from eos_procurement.infrastructure import budget_grants

    html = httpx.MockTransport(lambda req: httpx.Response(200, text="<html>proxy error</html>"))
    monkeypatch.setattr(budget_grants, "client_factory", lambda: httpx.Client(transport=html))
    i = _indent(client, org).json()
    client.post(f"{BASE}/indents/{i['id']}/submit", headers=org.faculty)
    r = client.post(f"{BASE}/indents/{i['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 503 and r.json()["detail"]["code"] == "budget_check_unavailable"
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.manager).json()["status"] == "submitted"


def test_a_vendor_validation_error_never_echoes_the_account_number(client, org):
    bank = {"account_number": "123456789012", "ifsc": "SBIN0001234"}
    for body in ({"categories": ["IT"], "bank_account": bank}, {"name": "x", "categories": "IT", "bank_account": bank}):
        r = client.post(f"{BASE}/vendors", json=body, headers=org.staff)
        assert r.status_code == 422 and "123456789012" not in r.text
        assert r.json()["detail"][0]["loc"][0] == "body"
    v = vendor(client, org)
    r = client.put(f"{BASE}/vendors/{v['id']}", json={"categories": ["IT"], "bank_account": bank}, headers=org.staff)
    assert r.status_code == 422 and "123456789012" not in r.text


def test_reopening_indents_after_a_cancelled_order_is_audited_as_such(client, org):
    po = issued_order(client, org)
    client.post(f"{BASE}/purchase-orders/{po['id']}/cancel", json={"reason": "not needed"}, headers=org.manager)
    [indent_id] = po["indent_ids"]
    with SessionLocal() as db, platform_scope():
        q = select(AuditEntry.action).where(AuditEntry.entity_id == indent_id).order_by(AuditEntry.occurred_at)
        actions = list(db.scalars(q))
    assert actions.count("indent.approved") == 1 and "indent.reopened" in actions


def test_an_earlier_preparer_cannot_approve_after_someone_else_submits(client, org):
    """A creates the order, B submits it (prepared_by becomes B): A still may not approve it."""
    from eos_core.db import new_id
    from eos_core.security import create_token
    from pc_support import TODAY, approved_indent, auth, item, vendor

    # a real user id: identity issues UUIDs, and every user column is String(36) (Postgres refuses longer ones)
    dual = auth(create_token(user_id=new_id(), organisation_id=org.id, roles=["finance-staff", "management"]))
    i = approved_indent(client, org)
    v = vendor(client, org)
    body = {"vendor_id": v["id"], "indent_ids": [i["id"]], "items": [item()], "delivery_by": TODAY}
    po = client.post(f"{BASE}/purchase-orders", json=body, headers=dual).json()
    assert client.post(f"{BASE}/purchase-orders/{po['id']}/submit", headers=org.staff2).status_code == 200
    r = client.post(f"{BASE}/purchase-orders/{po['id']}/decision", json={"decision": "approved"}, headers=dual)
    assert r.status_code == 403, r.text
    r = client.post(f"{BASE}/purchase-orders/{po['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 200, r.text


def test_a_draft_or_returned_order_can_be_cancelled_and_frees_its_indents(client, org):
    """Second review: an order that was never issued could not be cancelled, so its indents stayed held."""
    from pc_support import outbox

    i = approved_indent(client, org)
    draft = _order(client, org, [i], [item()]).json()
    r = client.post(
        f"{BASE}/purchase-orders/{draft['id']}/cancel", json={"reason": "wrong vendor"}, headers=org.manager
    )
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert not [
        e for e in outbox("procurement.purchase-order.cancelled", org.id) if e["purchase_order_id"] == draft["id"]
    ]
    assert client.get(f"{BASE}/indents/{i['id']}", headers=org.manager).json()["status"] == "approved"
    again = _order(client, org, [i], [item()])  # the indent is free again
    assert again.status_code == 201
    po = again.json()
    client.post(f"{BASE}/purchase-orders/{po['id']}/submit", headers=org.staff)
    client.post(f"{BASE}/purchase-orders/{po['id']}/decision", json={"decision": "returned"}, headers=org.manager)
    r = client.post(f"{BASE}/purchase-orders/{po['id']}/cancel", json={"reason": "not needed"}, headers=org.manager)
    assert r.json()["status"] == "cancelled"
    for status_po in (draft, po):  # a cancelled order is not cancelled twice
        r = client.post(f"{BASE}/purchase-orders/{status_po['id']}/cancel", json={"reason": "x"}, headers=org.manager)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "not_cancellable"
    submitted = _order(client, org, [approved_indent(client, org)], [item()]).json()
    client.post(f"{BASE}/purchase-orders/{submitted['id']}/submit", headers=org.staff)
    r = client.post(f"{BASE}/purchase-orders/{submitted['id']}/cancel", json={"reason": "x"}, headers=org.manager)
    assert r.status_code == 409  # a submitted order is decided first (returned, then cancelled)


def test_order_and_receipt_dates_cannot_precede_the_order(client, org, monkeypatch):
    """Second review: delivery_by and received_on accepted dates before the order."""
    from eos_procurement.application import service

    yesterday = (NOW - timedelta(days=1)).date().isoformat()
    r = _order(client, org, [approved_indent(client, org)], [item()], delivery_by=yesterday)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"
    po = _order(client, org, [approved_indent(client, org)], [item()], delivery_by=TODAY).json()  # today is fine
    edit = {"vendor_id": po["vendor_id"], "indent_ids": po["indent_ids"], "items": [item()], "delivery_by": yesterday}
    assert client.put(f"{BASE}/purchase-orders/{po['id']}", json=edit, headers=org.staff).status_code == 422
    _later(monkeypatch, days=2)  # the draft waited past its delivery date
    r = client.post(f"{BASE}/purchase-orders/{po['id']}/submit", headers=org.staff)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"
    monkeypatch.setattr(service, "clock", lambda: NOW)
    issued = issued_order(client, org)  # issued today (IST)
    r = receive(client, org, issued, (0, 1, 1), received_on=yesterday)
    assert r.status_code == 422 and "before the order was issued" in r.json()["detail"]["message"]
    assert receive(client, org, issued, (0, 1, 1), received_on=TODAY).status_code == 201


# ---------------------------------------------------------------- third review (#295)


def _published(client, org, cost="60000.00"):
    ind = approved_indent(client, org, cost)
    t = _tender(client, org, ind).json()
    assert client.post(f"{BASE}/tenders/{t['id']}/publish", headers=org.staff).status_code == 200
    return ind, t


def _quote(client, org, t, v, total, items, **fields):
    body = {"vendor_id": v["id"], "items": items, "total": total, **fields}
    return client.post(f"{BASE}/tenders/{t['id']}/quotes", json=body, headers=org.staff)


def test_a_quotes_total_must_be_its_items_total(client, org, monkeypatch):
    """The reviewer's case: vendor A typed total 1000 with items 2 x 40000, ranked first and was awarded at 80000."""
    a, b = vendor(client, org), vendor(client, org)
    vendor(client, org)  # the category needs an approved vendor to publish
    _, t = _published(client, org)
    r = _quote(client, org, t, a, "1000", [item(2, "40000.00")])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "quote_total_mismatch"
    assert "80000.00" in r.json()["detail"]["message"]
    r = _quote(client, org, t, a, "1000", [item(2, None)])  # an unpriced item
    assert r.status_code == 422 and r.json()["detail"]["code"] == "price_required"
    assert _quote(client, org, t, a, "1000", []).status_code == 422  # items are required
    with_tax = [item(2, "25000.00", tax_percent=18)]  # 50000 + 18% = 59000
    assert _quote(client, org, t, b, "50000", with_tax).json()["detail"]["code"] == "quote_total_mismatch"
    assert _quote(client, org, t, b, "59000", with_tax).status_code == 201
    assert _quote(client, org, t, a, "80000", [item(2, "40000.00")]).status_code == 201
    _later(monkeypatch)
    quotes = client.get(f"{BASE}/tenders/{t['id']}", headers=org.staff).json()["quotes"]
    assert [q["total"] for q in quotes] == ["59000.00", "80000.00"]  # ranked by the real totals
    po = client.post(f"{BASE}/tenders/{t['id']}/award", json={"quote_id": quotes[0]["id"]}, headers=org.staff).json()
    assert po["total"] == "59000.00"  # the order is priced exactly as the quote that won


def test_a_tender_whose_quotes_cannot_be_awarded_lets_its_indents_go(client, org, monkeypatch):
    """The reviewer's case: a closed tender with only an expired quote, or only a quote from a vendor no longer
    approved, could never be awarded but kept its indents locked."""
    v = vendor(client, org)
    expired_ind, t1 = _published(client, org)
    _quote(client, org, t1, v, "50000", [item(1, "50000.00")], valid_until="2026-11-01")
    blocked_ind, t2 = _published(client, org)
    w = vendor(client, org)
    _quote(client, org, t2, w, "50000", [item(1, "50000.00")])
    client.post(
        f"{BASE}/vendors/{w['id']}/status", json={"status": "blacklisted", "reason": "fraud"}, headers=org.staff
    )
    live_ind, t3 = _published(client, org)
    _quote(client, org, t3, v, "50000", [item(1, "50000.00")])
    _later(monkeypatch)  # 5 November: all three closed; the first quote expired on the 1st
    again = (NOW + timedelta(days=20)).isoformat()
    assert _tender(client, org, expired_ind, again).status_code == 201
    assert _tender(client, org, blocked_ind, again).status_code == 201
    r = _tender(client, org, live_ind, again)  # its quote can still be awarded: the indent stays with it
    assert r.status_code == 409 and r.json()["detail"]["code"] == "indent_in_use"


def test_an_awarded_order_keeps_the_quotes_items_and_prices(client, org, monkeypatch):
    """The reviewer's case: a 50000 quotation award was raised to 800000 with no check."""
    v = vendor(client, org)
    vendor(client, org)
    _, t = _published(client, org)
    q = _quote(client, org, t, v, "50000", [item(1, "50000.00")]).json()["quotes"][0]
    _later(monkeypatch)
    po = client.post(f"{BASE}/tenders/{t['id']}/award", json={"quote_id": q["id"]}, headers=org.staff).json()
    body = {
        "vendor_id": po["vendor_id"],
        "indent_ids": po["indent_ids"],
        "items": [item(1, "800000.00")],
        "delivery_by": "2026-12-15",
    }
    r = client.put(f"{BASE}/purchase-orders/{po['id']}", json=body, headers=org.staff)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "awarded_order"
    body["items"] = [item(2, "25000.00")]  # same total, different items: still the award's items only
    assert client.put(f"{BASE}/purchase-orders/{po['id']}", json=body, headers=org.staff).status_code == 422
    body.update(items=po["items"], delivery_address="Stores, block B", terms="Net 30")
    r = client.put(f"{BASE}/purchase-orders/{po['id']}", json=body, headers=org.staff)
    assert r.status_code == 200, r.text
    assert r.json()["total"] == "50000.00" and r.json()["delivery_by"] == "2026-12-15" and r.json()["terms"] == "Net 30"


# ---------------------------------------------------------------- fourth review (#295)


def test_a_tender_cannot_award_indents_another_order_took_while_its_vendor_was_suspended(client, org, monkeypatch):
    """The reviewer's steps: T1 closes with V's quote; V is suspended, so T1 lets its indent go; T2 for the same
    indent is awarded (PO-00001); V is approved again, which made T1 awardable, and its award drafted PO-00002 for the
    same indent. The award now locks and checks the tender's indents."""
    v, w = vendor(client, org), vendor(client, org)
    ind, t1 = _published(client, org)
    q1 = _quote(client, org, t1, v, "50000", [item(1, "50000.00")]).json()["quotes"][0]
    _later(monkeypatch)  # T1 closed
    status = f"{BASE}/vendors/{v['id']}/status"
    assert client.post(status, json={"status": "suspended", "reason": "audit"}, headers=org.staff).status_code == 200
    t2 = _tender(client, org, ind, (NOW + timedelta(days=10)).isoformat())
    assert t2.status_code == 201, t2.text
    t2 = t2.json()
    assert client.post(f"{BASE}/tenders/{t2['id']}/publish", headers=org.staff).status_code == 200
    q2 = _quote(client, org, t2, w, "48000", [item(1, "48000.00")]).json()["quotes"][0]
    _later(monkeypatch, days=12)  # T2 closed
    award = f"{BASE}/tenders/{{}}/award"
    po1 = client.post(award.format(t2["id"]), json={"quote_id": q2["id"]}, headers=org.staff)
    assert po1.status_code == 200, po1.text
    assert client.post(status, json={"status": "approved", "reason": "cleared"}, headers=org.staff).status_code == 200
    r = client.post(award.format(t1["id"]), json={"quote_id": q1["id"]}, headers=org.staff)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "indent_in_use", r.text
    orders = client.get(f"{BASE}/purchase-orders", headers=org.staff).json()["items"]
    assert [o["id"] for o in orders if ind["id"] in o["indent_ids"]] == [po1.json()["id"]]  # one order per indent
    assert client.get(f"{BASE}/tenders/{t1['id']}", headers=org.staff).json()["status"] == "closed"  # not awarded
    # Once the other order is cancelled the indent is free, and T1 can be awarded after all.
    cancel = client.post(
        f"{BASE}/purchase-orders/{po1.json()['id']}/cancel", json={"reason": "wrong tender"}, headers=org.manager
    )
    assert cancel.status_code == 200, cancel.text
    assert client.post(award.format(t1["id"]), json={"quote_id": q1["id"]}, headers=org.staff).status_code == 200


def test_running_numbers_take_a_per_organisation_lock_on_postgres(client, org, monkeypatch):
    """_next_number locks per organisation and table before counting (as maintenance does), so two creates take turns.
    SQLite has a single writer, so the statement and its order are checked here with a stand-in Postgres session; the
    race itself was run on PostgreSQL 16 (both creates got a number; without the lock the second answered 409)."""
    from eos_core.db import SessionLocal
    from eos_procurement.application import service
    from eos_procurement.infrastructure.models import Indent

    calls = []

    class PostgresSession:
        """Delegates to a real session; reports the Postgres dialect and records what runs, in order."""

        def __init__(self, real):
            self.real, self.info = real, real.info

        def get_bind(self, *a, **k):
            return type("Bind", (), {"dialect": type("Dialect", (), {"name": "postgresql"})()})()

        def execute(self, stmt, params=None, **k):
            calls.append(("lock", str(stmt), params))

        def scalar(self, stmt, *a, **k):
            calls.append(("count",))
            return self.real.scalar(stmt, *a, **k)

    with SessionLocal() as real:
        real.info["organisation_id"] = org.id
        number = service._next_number(PostgresSession(real), Indent, "IND")
    assert number == "IND-00001"  # a fresh organisation
    assert calls == [
        (
            "lock",
            "SELECT pg_advisory_xact_lock(hashtext(:key))",
            {"key": f"procurement:number:procurement_indent:{org.id}"},
        ),
        ("count",),
    ]
