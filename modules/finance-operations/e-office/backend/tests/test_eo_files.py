"""Categories, opening files, the note sheet, attachments, forwarding, closing and reopening, movements, inbox and
sent: the holder rules (409), permissions (403) and validation (422)."""

import pytest
from eo_support import BASE, attach, category, forward, note, open_file, outbox


def test_categories_are_managed_by_settings_and_listed_to_file_users(client, org):
    c = category(client, org, "est", name="Establishment", retention_years=10)
    assert (c["code"], c["name"], c["retention_years"], c["active"]) == ("EST", "Establishment", 10, True)
    assert client.post(f"{BASE}/categories", json={"code": "EST", "name": "x"}, headers=org.admin).status_code == 409
    assert client.post(f"{BASE}/categories", json={"code": "NEW", "name": "x"}, headers=org.hr).status_code == 403
    r = client.put(
        f"{BASE}/categories/{c['id']}",
        json={"id": c["id"], "code": "EST", "name": "Est.", "active": False},
        headers=org.admin,
    )
    assert r.status_code == 200 and r.json()["active"] is False and r.json()["name"] == "Est."
    listed = client.get(f"{BASE}/categories", headers=org.hr).json()
    assert [x["code"] for x in listed] == ["EST"]
    assert client.get(f"{BASE}/categories", headers=org.nobody).status_code == 403
    other = category(client, org, "OTH")
    r = client.put(f"{BASE}/categories/{other['id']}", json={"code": "EST", "name": "x"}, headers=org.admin)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "category_exists"


@pytest.mark.parametrize(
    "body",
    [
        {"code": "A", "name": "x"},
        {"code": "AB CD", "name": "x"},
        {"code": "AB", "name": ""},
        {"code": "AB", "name": "x", "retention_years": -1},
        {"code": "AB", "name": "x", "colour": "red"},
    ],
)
def test_category_validation(client, org, body):
    assert client.post(f"{BASE}/categories", json=body, headers=org.admin).status_code == 422


def test_open_a_file(client, org):
    cat = category(client, org, "ADM")
    f = open_file(client, org, cat=cat, priority="urgent", department_id="d1", first_note="Please see the proposal.")
    assert f["number"] == "ADM/2026/0001"
    assert (f["status"], f["priority"], f["confidential"], f["department_id"]) == ("open", "urgent", False, "d1")
    assert f["holder"] == {"user_id": org.ids["hr"], "name": "", "designation": None}
    assert f["created_by"]["user_id"] == org.ids["hr"]
    assert [(n["sequence"], n["kind"], n["text"]) for n in f["notes"]] == [(1, "noting", "Please see the proposal.")]
    assert f["overdue"] is False and f["due_on"] is None and f["last_decision"] is None
    assert open_file(client, org, cat=cat)["number"] == "ADM/2026/0002"
    assert outbox("e-office.file.created", org.id)[0] == {
        "organisation_id": org.id,
        "file_id": f["id"],
        "number": "ADM/2026/0001",
        "category_id": cat["id"],
        "department_id": "d1",
        "created_by": org.ids["hr"],
        "confidential": False,
    }


def test_numbers_run_per_category_and_year(client, org, clock):
    a, b = category(client, org, "AA"), category(client, org, "BB")
    assert open_file(client, org, cat=a)["number"] == "AA/2026/0001"
    assert open_file(client, org, cat=b)["number"] == "BB/2026/0001"
    clock.advance(days=62)  # 1 January 2027 in India
    assert open_file(client, org, cat=a)["number"] == "AA/2027/0001"


def test_opening_needs_permission_and_an_active_category(client, org):
    cat = category(client, org)
    r = client.post(f"{BASE}/files", json={"subject": "x", "category_id": cat["id"]}, headers=org.admin)
    assert r.status_code == 403  # org-admin can use files but not open them
    r = client.post(f"{BASE}/files", json={"subject": "x", "category_id": "missing"}, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_category"
    client.put(
        f"{BASE}/categories/{cat['id']}", json={"code": cat["code"], "name": "x", "active": False}, headers=org.admin
    )
    r = client.post(f"{BASE}/files", json={"subject": "x", "category_id": cat["id"]}, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "inactive_category"


@pytest.mark.parametrize(
    "body",
    [
        {"subject": ""},
        {"subject": "x" * 501},
        {"subject": "x", "priority": "high"},
        {"subject": "x", "number": "ADM/1"},
        {},
    ],
)
def test_file_validation(client, org, body):
    cat = category(client, org)
    r = client.post(f"{BASE}/files", json={"category_id": cat["id"], **body}, headers=org.hr)
    assert r.status_code == 422


def test_blank_subject_after_trimming_is_422(client, org):
    cat = category(client, org)
    r = client.post(f"{BASE}/files", json={"subject": "   ", "category_id": cat["id"]}, headers=org.hr)
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_subject"


def test_notings_are_numbered_and_only_the_holder_adds_them(client, org):
    f = open_file(client, org, first_note="Opening.")
    r = note(client, org, f, "hr", "Second paragraph.")
    assert r.status_code == 201 and (r.json()["sequence"], r.json()["kind"]) == (2, "noting")
    assert forward(client, org, f, "hr", "finance").status_code == 200
    r = note(client, org, f, "hr", "Too late.")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_holder"
    assert note(client, org, f, "finance", "Third.").json()["sequence"] == 3
    notes = client.get(f"{BASE}/files/{f['id']}", headers=org.finance).json()["notes"]
    assert [(n["sequence"], n["text"]) for n in notes] == [(1, "Opening."), (2, "Second paragraph."), (3, "Third.")]
    assert notes[1]["author"]["user_id"] == org.ids["hr"] and notes[2]["author"]["user_id"] == org.ids["finance"]


def test_the_note_sheet_cannot_be_edited_or_deleted(client, org):
    from eos_e_office.api.router import router

    f = open_file(client, org, first_note="Opening.")
    paths = [r.path + ":" + ",".join(sorted(r.methods)) for r in router.routes if "/notes" in r.path]
    assert paths == ["/files/{file_id}/notes:POST"]
    for method in ("put", "patch", "delete"):
        assert getattr(client, method)(f"{BASE}/files/{f['id']}/notes", headers=org.hr).status_code == 405


def test_noting_validation_and_attachment_references(client, org):
    f = open_file(client, org)
    other = open_file(client, org)
    a = attach(client, org, f, "hr").json()
    elsewhere = attach(client, org, other, "hr").json()
    assert note(client, org, f, "hr", "").status_code == 422
    assert note(client, org, f, "hr", "  ").json()["detail"]["code"] == "invalid_text"
    r = note(client, org, f, "hr", "See the draft.", attachment_ids=[a["id"]])
    assert r.status_code == 201 and r.json()["attachment_ids"] == [a["id"]]
    r = note(client, org, f, "hr", "See the other draft.", attachment_ids=[elsewhere["id"]])
    assert r.status_code == 422 and r.json()["detail"]["code"] == "unknown_attachment"


def test_attachments_are_document_ids_added_by_the_holder(client, org):
    f = open_file(client, org)
    r = attach(client, org, f, "hr", document_id="doc-42", title="Proposal", kind="draft")
    assert r.status_code == 201
    a = r.json()
    assert (a["document_id"], a["title"], a["kind"], a["receipt_id"]) == ("doc-42", "Proposal", "draft", None)
    assert a["added_by"]["user_id"] == org.ids["hr"]
    assert attach(client, org, f, "hr", kind="memo").status_code == 422
    assert attach(client, org, f, "hr", document_id="").status_code == 422
    forward(client, org, f, "hr", "finance")
    assert attach(client, org, f, "hr").json()["detail"]["code"] == "not_holder"
    got = client.get(f"{BASE}/files/{f['id']}", headers=org.hr).json()
    assert [x["id"] for x in got["attachments"]] == [a["id"]]


def test_forwarding_moves_the_file_and_publishes_without_note_text(client, org, clock):
    f = open_file(client, org, first_note="Secret reasoning.", priority="immediate")
    clock.advance(hours=3)
    r = forward(
        client, org, f, "hr", "finance", remark="Please examine", action_required="for comments", due_on="2026-11-03"
    )
    assert r.status_code == 200, r.text
    moved = r.json()
    assert moved["holder"]["user_id"] == org.ids["finance"]
    assert (moved["action_required"], moved["due_on"]) == ("for comments", "2026-11-03")
    assert moved["held_since"].startswith("2026-10-31T09:00")
    event = outbox("e-office.file.forwarded", org.id)[-1]
    assert event == {
        "organisation_id": org.id,
        "file_id": f["id"],
        "number": f["number"],
        "subject": f["subject"],
        "from_user_id": org.ids["hr"],
        "to_user_id": org.ids["finance"],
        "action_required": "for comments",
        "priority": "immediate",
        "due_on": "2026-11-03",
    }
    assert "Secret" not in str(outbox("e-office.file.forwarded", org.id) + outbox("e-office.file.created", org.id))
    history = client.get(f"{BASE}/files/{f['id']}/movements", headers=org.finance).json()
    assert [(m["kind"], (m["from"] or {}).get("user_id"), m["to"]["user_id"]) for m in history] == [
        ("created", None, org.ids["hr"]),
        ("forwarded", org.ids["hr"], org.ids["finance"]),
    ]
    assert history[1]["held_for_hours"] == 3.0 and history[1]["remark"] == "Please examine"


def test_forwarding_rules(client, org):
    f = open_file(client, org)
    r = forward(client, org, f, "hr", "hr")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "same_holder"
    r = forward(client, org, f, "hr", "finance", due_on="2026-10-30")
    assert r.status_code == 422 and r.json()["detail"]["code"] == "invalid_date"
    assert forward(client, org, f, "hr", "finance", due_on="2026-10-31").status_code == 200
    r = forward(client, org, f, "hr", "dept")
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_holder"
    r = client.post(f"{BASE}/files/{f['id']}/forward", json={}, headers=org.finance)
    assert r.status_code == 422
    assert forward(client, org, f, "nobody", "dept").status_code == 403


def test_a_file_one_never_held_is_404(client, org):
    f = open_file(client, org)
    assert client.get(f"{BASE}/files/{f['id']}", headers=org.finance).status_code == 404
    assert note(client, org, f, "finance").status_code == 404
    assert forward(client, org, f, "finance", "dept").status_code == 404
    assert client.get(f"{BASE}/files/{f['id']}/movements", headers=org.finance).status_code == 404
    assert client.get(f"{BASE}/files/missing", headers=org.hr).status_code == 404


def test_close_and_reopen(client, org):
    f = open_file(client, org)
    forward(client, org, f, "hr", "finance")
    r = client.post(f"{BASE}/files/{f['id']}/close", json={"remark": "Done"}, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_holder"
    assert client.post(f"{BASE}/files/{f['id']}/close", json={"remark": ""}, headers=org.finance).status_code == 422
    r = client.post(f"{BASE}/files/{f['id']}/close", json={"remark": "Action complete"}, headers=org.finance)
    assert r.status_code == 200
    closed = r.json()
    assert closed["status"] == "closed" and closed["closed_at"] and closed["notes"][-1]["kind"] == "system"
    assert outbox("e-office.file.closed", org.id) == [
        {"organisation_id": org.id, "file_id": f["id"], "number": f["number"], "closed_by": org.ids["finance"]}
    ]
    # no further movement until reopened
    assert note(client, org, f, "finance").json()["detail"]["code"] == "file_closed"
    assert forward(client, org, f, "finance", "hr").json()["detail"]["code"] == "file_closed"
    r = client.post(f"{BASE}/files/{f['id']}/close", json={"remark": "again"}, headers=org.finance)
    assert r.json()["detail"]["code"] == "file_closed"
    # finance-staff has file:create; the department admin never held it, so it is 404 to them
    assert client.post(f"{BASE}/files/{f['id']}/reopen", json={"remark": "x"}, headers=org.dept).status_code == 404
    assert client.post(f"{BASE}/files/{f['id']}/reopen", json={"remark": "x"}, headers=org.admin).status_code == 403
    r = client.post(f"{BASE}/files/{f['id']}/reopen", json={"remark": "New facts"}, headers=org.hr)
    assert r.status_code == 200
    reopened = r.json()
    assert reopened["status"] == "open" and reopened["closed_at"] is None
    assert reopened["holder"]["user_id"] == org.ids["hr"]
    assert reopened["notes"][-1]["text"] == "File reopened. New facts"
    r = client.post(f"{BASE}/files/{f['id']}/reopen", json={"remark": "x"}, headers=org.hr)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "not_closed"
    kinds = [m["kind"] for m in client.get(f"{BASE}/files/{f['id']}/movements", headers=org.hr).json()]
    assert kinds == ["created", "forwarded", "closed", "reopened"]


def test_inbox_lists_open_files_held_oldest_first_with_counts(client, org, clock):
    empty = client.get(f"{BASE}/me/inbox", headers=org.finance).json()
    assert empty == {
        "total": 0,
        "overdue": 0,
        "urgent": 0,
        "oldest_held_since": None,
        "items": [],
        "unattached_receipts": 0,
        "next_cursor": None,
    }
    first = open_file(client, org, priority="urgent")
    clock.advance(hours=1)
    second = open_file(client, org)
    clock.advance(hours=1)
    third = open_file(client, org, priority="immediate")
    forward(client, org, first, "hr", "finance")
    clock.advance(hours=1)
    forward(client, org, second, "hr", "finance")
    forward(client, org, third, "hr", "finance")
    closed = open_file(client, org)
    forward(client, org, closed, "hr", "finance")
    client.post(f"{BASE}/files/{closed['id']}/close", json={"remark": "x"}, headers=org.finance)
    inbox = client.get(f"{BASE}/me/inbox?limit=2", headers=org.finance).json()
    assert (inbox["total"], inbox["urgent"], inbox["overdue"]) == (3, 2, 0)
    assert [x["id"] for x in inbox["items"]] == [first["id"], second["id"]]
    assert inbox["oldest_held_since"] == inbox["items"][0]["held_since"] and inbox["next_cursor"] == "2"
    rest = client.get(f"{BASE}/me/inbox?limit=2&cursor=2", headers=org.finance).json()
    assert [x["id"] for x in rest["items"]] == [third["id"]] and rest["next_cursor"] is None
    assert client.get(f"{BASE}/me/inbox", headers=org.hr).json()["total"] == 0
    assert client.get(f"{BASE}/me/inbox", headers=org.nobody).status_code == 403
    assert client.get(f"{BASE}/me/inbox?cursor=x", headers=org.hr).status_code == 400
    assert client.get(f"{BASE}/me/inbox?limit=0", headers=org.hr).status_code == 422


def test_sent_lists_what_one_forwarded_and_where_it_is_now(client, org, clock):
    a, b = open_file(client, org), open_file(client, org)
    forward(client, org, a, "hr", "finance")
    clock.advance(minutes=5)
    forward(client, org, b, "hr", "finance")
    forward(client, org, a, "finance", "dept")
    items = client.get(f"{BASE}/me/sent", headers=org.hr).json()["items"]
    assert [x["id"] for x in items] == [b["id"], a["id"]]
    assert items[1]["holder"]["user_id"] == org.ids["dept"]
    assert [x["id"] for x in client.get(f"{BASE}/me/sent", headers=org.finance).json()["items"]] == [a["id"]]
    assert client.get(f"{BASE}/me/sent", headers=org.dept).json()["items"] == []


def test_list_files_filters_and_search(client, org):
    cat = category(client, org, "SRCH")
    a = open_file(client, org, cat=cat, subject="Annual sports day budget", department_id="d1")
    b = open_file(client, org, subject="Hostel repairs")
    forward(client, org, b, "hr", "finance")

    def ids(query: str) -> list[str]:
        r = client.get(f"{BASE}/files{query}", headers=org.hr)
        assert r.status_code == 200, r.text
        return [x["id"] for x in r.json()["items"]]

    assert set(ids("")) >= {a["id"], b["id"]}
    assert ids("?q=SPORTS") == [a["id"]]
    assert ids("?q=srch/2026") == [a["id"]]
    assert ids(f"?category_id={cat['id']}") == [a["id"]]
    assert ids("?department_id=d1") == [a["id"]]
    assert b["id"] in ids(f"?holder_id={org.ids['finance']}")
    assert ids("?status=closed") == []
    assert client.get(f"{BASE}/files?status=archived", headers=org.hr).status_code == 422
