"""Inward receipts (register, send, attach to a file or open a new one) and outward dispatch (request from an approved
file, mark sent by the registry)."""

from eo_support import BASE, TODAY, approved_file, attach, category, decide, forward, open_file, outbox, receipt


def test_the_registry_registers_a_receipt_and_the_recipient_is_told(client, org):
    r = receipt(client, org, sender_reference="DE/12/2026")
    assert r["number"] == "IN/2026/00001" and r["status"] == "registered" and r["file_id"] is None
    assert (r["sender_reference"], r["mode"], r["document_id"]) == ("DE/12/2026", "post", "scan-1")
    assert r["registered_by"]["user_id"] == org.ids["hr"]
    assert receipt(client, org)["number"] == "IN/2026/00002"
    assert outbox("e-office.receipt.registered", org.id)[0] == {
        "organisation_id": org.id,
        "receipt_id": r["id"],
        "number": "IN/2026/00001",
        "send_to_user_id": org.ids["hr2"],
        "received_on": TODAY,
    }
    inbox = client.get(f"{BASE}/me/inbox", headers=org.hr2).json()
    assert inbox["unattached_receipts"] == 2 and inbox["total"] == 0
    mine = client.get(f"{BASE}/me/receipts?status=registered", headers=org.hr2).json()["items"]
    assert {x["id"] for x in mine} >= {r["id"]}


def test_a_receipt_without_a_scan_is_allowed_until_documents_exists(client, org):
    r = receipt(client, org, document_id=None, mode=None)
    assert r["document_id"] is None and r["mode"] is None


def test_receipt_rules_and_permissions(client, org):
    body = {"received_on": TODAY, "sender": "x", "subject": "y", "send_to_user_id": org.ids["finance"]}
    assert client.post(f"{BASE}/receipts", json=body, headers=org.finance).status_code == 403
    assert client.get(f"{BASE}/receipts", headers=org.finance).status_code == 403
    r = client.post(f"{BASE}/receipts", json={**body, "received_on": "2026-11-01"}, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"
    assert client.post(f"{BASE}/receipts", json={**body, "mode": "fax"}, headers=org.hr).status_code == 422
    assert client.post(f"{BASE}/receipts", json={**body, "sender": ""}, headers=org.hr).status_code == 422
    r = client.post(f"{BASE}/receipts", json={**body, "sender": " "}, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_sender"


def test_who_can_read_a_receipt(client, org):
    r = receipt(client, org, to="finance")
    assert client.get(f"{BASE}/receipts/{r['id']}", headers=org.hr).status_code == 200  # the registry
    assert client.get(f"{BASE}/receipts/{r['id']}", headers=org.finance).status_code == 200  # the recipient
    assert client.get(f"{BASE}/receipts/{r['id']}", headers=org.dept).status_code == 404
    assert client.get(f"{BASE}/receipts/{r['id']}", headers=org.nobody).status_code == 403


def test_receipt_list_filters(client, org):
    old = receipt(client, org, received_on="2026-10-20")
    new = receipt(client, org)
    items = client.get(f"{BASE}/receipts", headers=org.hr).json()["items"]
    assert [x["id"] for x in items][:2] == [new["id"], old["id"]]
    ranged = client.get(f"{BASE}/receipts?from=2026-10-19&to=2026-10-21", headers=org.hr).json()["items"]
    assert [x["id"] for x in ranged if x["organisation_id"] == org.id] == [old["id"]]
    assert client.get(f"{BASE}/receipts?status=filed", headers=org.hr).status_code == 422


def test_attach_a_receipt_to_a_held_file(client, org):
    r = receipt(client, org, to="finance")
    f = open_file(client, org, who="finance")
    other = open_file(client, org, who="hr")
    res = client.post(f"{BASE}/receipts/{r['id']}/attach", json={"file_id": other["id"]}, headers=org.finance)
    assert res.status_code == 404  # finance never held hr's file
    res = client.post(f"{BASE}/receipts/{r['id']}/attach", json={"file_id": f["id"]}, headers=org.hr)
    assert res.status_code == 403  # the registry sees it but it was sent to finance
    res = client.post(f"{BASE}/receipts/{r['id']}/attach", json={"file_id": f["id"]}, headers=org.finance)
    assert res.status_code == 200, res.text
    assert (res.json()["status"], res.json()["file_id"]) == ("attached", f["id"])
    got = client.get(f"{BASE}/files/{f['id']}", headers=org.finance).json()
    assert [(a["kind"], a["receipt_id"], a["document_id"]) for a in got["attachments"]] == [
        ("correspondence", r["id"], "scan-1")
    ]
    assert got["notes"][-1]["kind"] == "system" and r["number"] in got["notes"][-1]["text"]
    res = client.post(f"{BASE}/receipts/{r['id']}/attach", json={"file_id": f["id"]}, headers=org.finance)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "receipt_attached"
    assert client.get(f"{BASE}/me/inbox", headers=org.finance).json()["unattached_receipts"] == 0


def test_attaching_needs_the_file_in_hand(client, org):
    r = receipt(client, org, to="finance")
    f = open_file(client, org, who="finance")
    forward(client, org, f, "finance", "hr")
    res = client.post(f"{BASE}/receipts/{r['id']}/attach", json={"file_id": f["id"]}, headers=org.finance)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "not_holder"
    assert client.get(f"{BASE}/receipts/{r['id']}", headers=org.finance).json()["status"] == "registered"


def test_open_a_new_file_from_a_receipt(client, org):
    r = receipt(client, org, to="finance")
    cat = category(client, org)
    f = open_file(client, org, who="finance", cat=cat, receipt_id=r["id"], first_note="Received the circular.")
    assert [n["sequence"] for n in f["notes"]] == [1, 2]
    assert f["attachments"][0]["receipt_id"] == r["id"]
    assert client.get(f"{BASE}/receipts/{r['id']}", headers=org.finance).json()["file_id"] == f["id"]
    body = {"subject": "again", "category_id": cat["id"], "receipt_id": r["id"]}
    res = client.post(f"{BASE}/files", json=body, headers=org.finance)
    assert res.status_code == 409 and res.json()["detail"]["code"] == "receipt_attached"
    other = receipt(client, org, to="dept")
    res = client.post(f"{BASE}/files", json={**body, "receipt_id": other["id"]}, headers=org.finance)
    assert res.status_code == 404  # not sent to finance, and finance is not the registry


def test_dispatch_from_an_approved_file(client, org):
    f, letter = approved_file(client, org)
    r = client.post(
        f"{BASE}/dispatches",
        json={
            "file_id": f["id"],
            "attachment_id": letter["id"],
            "addressee": "The Director",
            "email": "dir@example.org",
        },
        headers=org.hr,
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert (d["number"], d["status"], d["file_number"], d["mode"]) == ("OUT/2026/00001", "pending", f["number"], None)
    again = client.post(
        f"{BASE}/dispatches",
        json={"file_id": f["id"], "attachment_id": letter["id"], "addressee": "The Director"},
        headers=org.hr,
    )
    assert again.status_code == 409 and again.json()["detail"]["code"] == "dispatch_exists"
    pending = client.get(f"{BASE}/dispatches?status=pending", headers=org.hr).json()["items"]
    assert [x["id"] for x in pending] == [d["id"]]
    assert client.get(f"{BASE}/dispatches", headers=org.finance).status_code == 403
    # the registry records how it went; the file is closed meanwhile and still records the number
    client.post(f"{BASE}/files/{f['id']}/close", json={"remark": "Letter issued"}, headers=org.hr)
    sent = {"mode": "email", "sent_on": TODAY, "reference": "msg-1"}
    assert client.post(f"{BASE}/dispatches/{d['id']}/mark-sent", json=sent, headers=org.finance).status_code == 403
    r = client.post(f"{BASE}/dispatches/{d['id']}/mark-sent", json=sent, headers=org.hr2)
    assert r.status_code == 200, r.text
    assert (r.json()["status"], r.json()["mode"], r.json()["sent_on"], r.json()["reference"]) == (
        "sent",
        "email",
        TODAY,
        "msg-1",
    )
    assert outbox("e-office.dispatch.sent", org.id) == [
        {
            "organisation_id": org.id,
            "dispatch_id": d["id"],
            "number": "OUT/2026/00001",
            "file_id": f["id"],
            "mode": "email",
            "sent_on": TODAY,
        }
    ]
    notes = client.get(f"{BASE}/files/{f['id']}", headers=org.hr).json()["notes"]
    assert "OUT/2026/00001 sent by email" in notes[-1]["text"]
    r = client.post(f"{BASE}/dispatches/{d['id']}/mark-sent", json=sent, headers=org.hr2)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "already_sent"


def test_dispatch_needs_approval_a_letter_of_the_file_and_the_holder(client, org):
    f = open_file(client, org)
    letter = attach(client, org, f, "hr").json()
    body = {"file_id": f["id"], "attachment_id": letter["id"], "addressee": "The Director"}
    r = client.post(f"{BASE}/dispatches", json=body, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_approved"
    forward(client, org, f, "hr", "dept")
    decide(client, org, f, "dept", "rejected")
    r = client.post(f"{BASE}/dispatches", json=body, headers=org.dept)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_approved"
    approved, approved_letter = approved_file(client, org)
    r = client.post(
        f"{BASE}/dispatches", json={**body, "file_id": approved["id"], "attachment_id": letter["id"]}, headers=org.hr
    )
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_attachment"
    r = client.post(
        f"{BASE}/dispatches",
        json={**body, "file_id": approved["id"], "attachment_id": approved_letter["id"]},
        headers=org.dept,
    )
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_holder"
    bad = {**body, "file_id": approved["id"], "attachment_id": approved_letter["id"], "email": "not-an-email"}
    assert client.post(f"{BASE}/dispatches", json=bad, headers=org.hr).status_code == 422


def test_mark_sent_dates(client, org, clock):
    f, letter = approved_file(client, org)
    body = {"file_id": f["id"], "attachment_id": letter["id"], "addressee": "The Registrar"}
    d = client.post(f"{BASE}/dispatches", json=body, headers=org.hr).json()
    for sent_on in ("2026-11-01", "2026-10-30"):
        r = client.post(
            f"{BASE}/dispatches/{d['id']}/mark-sent", json={"mode": "post", "sent_on": sent_on}, headers=org.hr
        )
        assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date", sent_on
    r = client.post(f"{BASE}/dispatches/{d['id']}/mark-sent", json={"mode": "pigeon", "sent_on": TODAY}, headers=org.hr)
    assert r.status_code == 422
    assert (
        client.post(
            f"{BASE}/dispatches/missing/mark-sent", json={"mode": "post", "sent_on": TODAY}, headers=org.hr
        ).status_code
        == 404
    )
