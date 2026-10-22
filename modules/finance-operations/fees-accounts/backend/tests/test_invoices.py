"""Raising, listing, reading and cancelling invoices (stories F3, F4, F8)."""

from fees_support import BASE, adhoc, head, invoice, outbox, pay_cash, published


def test_invoice_from_structure_instalment(client, org):
    h1, h2 = head(client, org, "TUI3"), head(client, org, "LIB3", "library")
    s = published(client, org, [h1, h2])
    inv = invoice(client, org, structure=s, instalment=1)
    assert inv["total"] == "24000.00" and inv["balance"] == "24000.00" and inv["status"] == "issued"
    assert [x["amount"] for x in inv["lines"]] == ["18000.00", "6000.00"]
    assert inv["due_date"] == "2026-10-31" and inv["instalment"] == 1
    assert inv["number"].startswith("INV-") and inv["academic_year"] == "2026-27"
    second = invoice(client, org, structure=s, instalment=2)
    assert second["total"] == "16000.00"
    assert int(second["number"].split("-")[1]) == int(inv["number"].split("-")[1]) + 1
    [issued] = [e for e in outbox("fees-accounts.invoice.issued", org.id) if e["invoice_id"] == inv["id"]]
    assert issued["person_id"] == org.ids["student"] and issued["total"] == "24000.00"


def test_one_live_invoice_per_instalment(client, org):
    s = published(client, org)
    inv = invoice(client, org, structure=s)
    body = {"person_id": org.ids["student"], "fee_structure_id": s["id"], "instalment": 1}
    again = client.post(f"{BASE}/invoices", json=body, headers=org.staff)
    assert again.status_code == 409 and again.json()["detail"]["code"] == "already_invoiced"
    client.post(f"{BASE}/invoices/{inv['id']}/cancel", json={"reason": "wrong person"}, headers=org.staff)
    assert client.post(f"{BASE}/invoices", json=body, headers=org.staff).status_code == 201


def test_invoice_needs_a_published_structure_and_valid_input(client, org):
    h = head(client, org, "TUI4")
    draft = client.post(
        f"{BASE}/fee-structures",
        json={
            "name": "Draft",
            "academic_year": "2026-27",
            "items": [{"fee_head_id": h["id"], "amount": "100"}],
            "instalments": [{"label": "All", "percent": 100, "due_date": "2026-11-01"}],
        },
        headers=org.staff,
    ).json()
    r = client.post(
        f"{BASE}/invoices",
        json={"person_id": org.ids["student"], "fee_structure_id": draft["id"], "instalment": 1},
        headers=org.staff,
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_published"
    assert client.post(f"{BASE}/invoices", json={"person_id": "p"}, headers=org.staff).status_code == 422
    s = published(client, org)
    r = client.post(
        f"{BASE}/invoices", json={"person_id": "p", "fee_structure_id": s["id"], "instalment": 9}, headers=org.staff
    )
    assert r.status_code == 422


def test_ad_hoc_invoice(client, org):
    inv = adhoc(client, org, "750.50", source={"module": "certificates", "reference": "CERT-9"})
    assert inv["total"] == "750.50" and inv["lines"][0]["description"] == "Lost ID card"
    assert inv["source"] == {"module": "certificates", "reference": "CERT-9"}
    assert inv["fee_structure_id"] is None and not inv["allow_part_payment"]


def test_bulk_skips_people_already_invoiced(client, org):
    s = published(client, org)
    invoice(client, org, "student", structure=s)
    people = [org.ids["student"], org.ids["classmate"], "person-3", "person-3"]
    r = client.post(
        f"{BASE}/invoices/bulk",
        json={"fee_structure_id": s["id"], "instalment": 1, "person_ids": people},
        headers=org.staff,
    )
    assert r.status_code == 202
    job = r.json()
    assert job == {**job, "status": "completed", "requested": 3, "created": 2, "skipped": 1, "errors": []}
    assert client.get(f"{BASE}/invoices/bulk/{job['id']}", headers=org.staff).json()["created"] == 2


def test_list_filters_and_pages(client, org):
    s = published(client, org)
    for person in ("p-a", "p-b", "p-c"):
        invoice(client, org, person, structure=s)
    page = client.get(f"{BASE}/invoices?fee_structure_id={s['id']}&limit=2", headers=org.staff).json()
    assert len(page["items"]) == 2 and page["next_cursor"]
    rest = client.get(
        f"{BASE}/invoices?fee_structure_id={s['id']}&limit=2&cursor={page['next_cursor']}", headers=org.staff
    ).json()
    assert len(rest["items"]) == 1 and rest["next_cursor"] is None
    assert client.get(f"{BASE}/invoices?person_id=p-a", headers=org.staff).json()["items"][0]["person_id"] == "p-a"
    overdue = adhoc(client, org, due="2026-10-01", person="p-late")
    late = client.get(f"{BASE}/invoices?overdue=true&person_id=p-late", headers=org.staff).json()["items"]
    assert [i["id"] for i in late] == [overdue["id"]] and late[0]["overdue"]
    assert client.get(f"{BASE}/invoices?cursor=-1", headers=org.staff).status_code == 400


def test_the_person_may_read_their_own_invoice(client, org):
    inv = adhoc(client, org)
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.student).status_code == 200
    assert client.get(f"{BASE}/invoices/{inv['id']}", headers=org.classmate).status_code == 404  # not revealed
    assert client.get(f"{BASE}/invoices/nope", headers=org.staff).status_code == 404


def test_cancel_only_without_payments(client, org):
    inv = adhoc(client, org)
    paid = adhoc(client, org)
    pay_cash(client, org, paid["id"], "100.00")
    r = client.post(f"{BASE}/invoices/{paid['id']}/cancel", json={"reason": "x"}, headers=org.staff)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "has_payments"
    r = client.post(f"{BASE}/invoices/{inv['id']}/cancel", json={"reason": "raised in error"}, headers=org.staff)
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert (
        client.post(f"{BASE}/invoices/{inv['id']}/cancel", json={"reason": "x"}, headers=org.staff).status_code == 409
    )
    [e] = [e for e in outbox("fees-accounts.invoice.cancelled", org.id) if e["invoice_id"] == inv["id"]]
    assert e["reason"] == "raised in error"
    assert (
        client.post(f"{BASE}/invoices/{inv['id']}/cancel", json={"reason": "x"}, headers=org.manager).status_code == 403
    )
