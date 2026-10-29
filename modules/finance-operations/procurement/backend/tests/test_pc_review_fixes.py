"""Regression tests for the defects an independent review of the backend found (#129)."""

from datetime import timedelta

import httpx
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from eos_procurement.infrastructure.models import AuditEntry
from pc_support import BASE, LATER, NOW, approved_indent, issued_order, item, vendor
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
    from eos_core.security import create_token
    from pc_support import TODAY, approved_indent, auth, item, vendor

    dual = auth(create_token(user_id="dual-" + org.id, organisation_id=org.id, roles=["finance-staff", "management"]))
    i = approved_indent(client, org)
    v = vendor(client, org)
    body = {"vendor_id": v["id"], "indent_ids": [i["id"]], "items": [item()], "delivery_by": TODAY}
    po = client.post(f"{BASE}/purchase-orders", json=body, headers=dual).json()
    assert client.post(f"{BASE}/purchase-orders/{po['id']}/submit", headers=org.staff2).status_code == 200
    r = client.post(f"{BASE}/purchase-orders/{po['id']}/decision", json={"decision": "approved"}, headers=dual)
    assert r.status_code == 403, r.text
    r = client.post(f"{BASE}/purchase-orders/{po['id']}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 200, r.text
