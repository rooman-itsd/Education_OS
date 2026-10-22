"""Concessions, statements, self-service dues and the dues read for other modules (F9, F10, M1, S1, S2, S4, X5)."""

from fees_support import BASE, adhoc, invoice, outbox, pay_cash, published


def test_concession_needs_someone_else_to_approve(client, org):
    inv = adhoc(client, org, "1000.00")
    c = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "scholarship", "percent": 25, "reason": "merit"},
        headers=org.staff,
    )
    assert c.status_code == 201 and c.json()["status"] == "requested" and c.json()["person_id"] == org.ids["student"]
    cid = c.json()["id"]
    assert client.get(f"{BASE}/concessions?status=requested", headers=org.manager).status_code == 200
    r = client.post(f"{BASE}/concessions/{cid}/decision", json={"decision": "approved"}, headers=org.staff)
    assert r.status_code == 403  # finance staff may request but not approve
    ok = client.post(
        f"{BASE}/concessions/{cid}/decision", json={"decision": "approved", "note": "ok"}, headers=org.manager
    )
    assert ok.json()["status"] == "approved" and ok.json()["approved_amount"] == "250.00"
    after = client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()
    assert after["concession_total"] == "250.00" and after["balance"] == "750.00"
    assert [
        e["approved_amount"] for e in outbox("fees-accounts.concession.approved", org.id) if e["concession_id"] == cid
    ] == ["250.00"]
    again = client.post(f"{BASE}/concessions/{cid}/decision", json={"decision": "rejected"}, headers=org.manager)
    assert again.status_code == 409


def test_concession_keeps_its_full_worth_and_can_settle_the_invoice(client, org):
    inv = adhoc(client, org, "1000.00")
    pay_cash(client, org, inv["id"], "900.00")
    cid = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "waiver", "amount": "500", "reason": "hardship"},
        headers=org.staff,
    ).json()["id"]
    r = client.post(f"{BASE}/concessions/{cid}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.json()["approved_amount"] == "500.00"  # the credit above what was due stays visible for a refund
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()["status"] == "paid"


def test_requester_can_never_decide_their_own(client, org):
    from eos_core.security import create_token

    inv = adhoc(client, org, "100.00")
    both = {
        "Authorization": f"Bearer {create_token(user_id=org.ids['manager'], organisation_id=org.id, roles=['finance-staff', 'management'])}"
    }
    cid = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "other", "amount": "10", "reason": "x"},
        headers=both,
    ).json()["id"]
    r = client.post(f"{BASE}/concessions/{cid}/decision", json={"decision": "approved"}, headers=org.manager)
    assert r.status_code == 403


def test_concession_input_is_amount_or_percent(client, org):
    inv = adhoc(client, org, "100.00")
    r = client.post(
        f"{BASE}/concessions", json={"invoice_id": inv["id"], "kind": "other", "reason": "x"}, headers=org.staff
    )
    assert r.status_code == 422
    rejected = client.post(
        f"{BASE}/concessions",
        json={"invoice_id": inv["id"], "kind": "other", "amount": "5", "reason": "x"},
        headers=org.staff,
    ).json()
    r = client.post(f"{BASE}/concessions/{rejected['id']}/decision", json={"decision": "rejected"}, headers=org.manager)
    assert r.json()["status"] == "rejected"
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.staff).json()["balance"] == "100.00"


def test_my_dues_invoices_and_receipts(client, org):
    s = published(client, org)
    first = invoice(client, org, structure=s, instalment=1)  # due 2026-10-31
    late = adhoc(client, org, "200.00", due="2026-10-01")
    paid = adhoc(client, org, "50.00")
    p = pay_cash(client, org, paid["id"], "50.00")
    dues = client.get(f"{BASE}/me/dues", headers=org.student).json()
    assert [i["id"] for i in dues["invoices"]] == [late["id"], first["id"]]
    assert dues["total_due"] == "18200.00" and dues["overdue"] == "200.00" and dues["next_due_date"] == "2026-10-31"
    assert dues["invoices"][0]["overdue"] and dues["invoices"][1]["title"] == "BSc 2026-27: Term 1"
    assert not dues["invoices"][0]["can_pay_online"]  # no adapter configured here
    assert client.get(f"{BASE}/me/dues", headers=org.classmate).json()["invoices"] == []
    mine = client.get(f"{BASE}/me/invoices", headers=org.student).json()["items"]
    assert {i["id"] for i in mine} == {first["id"], late["id"], paid["id"]}
    assert [r["payment_id"] for r in client.get(f"{BASE}/me/receipts", headers=org.student).json()] == [p["id"]]
    assert client.get(f"{BASE}/me/dues", headers=org.staff).status_code == 403
    assert client.get(f"{BASE}/me/dues", headers=org.applicant).status_code == 200


def test_can_pay_online_when_the_adapter_is_configured(client, org, adapter):
    adhoc(client, org, "10.00")
    assert client.get(f"{BASE}/me/dues", headers=org.student).json()["invoices"][0]["can_pay_online"]


def test_dues_for_examinations(client, org):
    exam = adhoc(client, org, "1500.00", source={"module": "examinations", "reference": "CYCLE-1"})
    adhoc(client, org, "700.00", source={"module": "hostel", "reference": "ALLOC-1"})
    q = f"{BASE}/dues?person_id={org.ids['student']}&source_module=examinations&source_reference=CYCLE-1"
    r = client.get(q, headers=org.exams).json()
    assert r["balance"] == "1500.00" and [i["id"] for i in r["invoices"]] == [exam["id"]]
    assert r["invoices"][0]["source"] == {"module": "examinations", "reference": "CYCLE-1"}
    everything = client.get(f"{BASE}/dues?person_id={org.ids['student']}", headers=org.staff).json()
    assert everything["balance"] == "2200.00"
    pay_cash(client, org, exam["id"], "1500.00")
    assert client.get(q, headers=org.exams).json()["balance"] == "0.00"
    assert client.get(f"{BASE}/dues?person_id=x&source_reference=CYCLE-1", headers=org.exams).status_code == 422
    assert client.get(f"{BASE}/dues?person_id=x", headers=org.student).status_code == 403


def test_statement_runs_a_balance(client, org):
    inv = adhoc(client, org, "1000.00", person="p-stmt")
    p = client.post(
        f"{BASE}/invoices/{inv['id']}/payments",
        json={"amount": "400", "mode": "cheque", "paid_on": "2026-10-22"},
        headers=org.staff,
    ).json()
    client.post(f"{BASE}/payments/{p['id']}/void", json={"reason": "bounced"}, headers=org.staff)
    pay_cash(client, org, inv["id"], "1000.00")
    st = client.get(f"{BASE}/accounts/p-stmt/statement", headers=org.staff).json()
    assert [e["kind"] for e in st["entries"]] == ["invoice", "payment", "payment", "void"]
    assert st["opening_balance"] == "0.00" and st["closing_balance"] == "0.00"
    later = client.get(f"{BASE}/accounts/p-stmt/statement?from=2026-10-23", headers=org.staff).json()
    assert later["entries"] == [] and later["opening_balance"] == "0.00"
    assert client.get(f"{BASE}/accounts/p-stmt/statement", headers=org.student).status_code == 403
