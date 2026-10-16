"""Integration tests through the HTTP API, against a throwaway SQLite database (see conftest)."""

from datetime import UTC, datetime, timedelta

from conftest import BASE, NOW
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_inventory_equipment.application import service
from eos_inventory_equipment.application.jobs import run_sweeps
from sqlalchemy import select

MANAGER = "inventory-equipment-manager"
APPROVER = "inventory-equipment-approver"
BORROWER = "inventory-equipment-borrower"


def due(days: float) -> str:
    return (NOW + timedelta(days=days)).isoformat()


def setup_store(client, mgr, *, category_rules=None, approvers=None, category="Equipment") -> tuple[dict, dict]:
    cat = client.post(
        f"{BASE}/categories",
        json={"name": category, "default_loan_rules": category_rules or {}, "approver_user_ids": approvers or []},
        headers=mgr,
    )
    assert cat.status_code == 201, cat.text
    loc = client.post(f"{BASE}/locations", json={"name": "Main store"}, headers=mgr)
    assert loc.status_code == 201, loc.text
    return cat.json(), loc.json()


def individual_item(client, mgr, cat, loc, *, tags=("U-1", "U-2"), **fields) -> dict:
    item = client.post(
        f"{BASE}/items",
        json={"name": "Camera", "category_id": cat["id"], "tracking": "individual"} | fields,
        headers=mgr,
    )
    assert item.status_code == 201, item.text
    for tag in tags:
        u = client.post(
            f"{BASE}/items/{item.json()['id']}/units", json={"tag": tag, "location_id": loc["id"]}, headers=mgr
        )
        assert u.status_code == 201, u.text
    return client.get(f"{BASE}/items/{item.json()['id']}", headers=mgr).json()


def quantity_item(client, mgr, cat, loc, *, on_hand=10, **fields) -> dict:
    item = client.post(
        f"{BASE}/items",
        json={"name": "Cable", "category_id": cat["id"], "tracking": "quantity", "unit_of_measure": "piece"} | fields,
        headers=mgr,
    ).json()
    if on_hand:
        r = client.post(
            f"{BASE}/movements",
            json={"kind": "receipt", "item_id": item["id"], "quantity": on_hand, "to_location_id": loc["id"]},
            headers=mgr,
        )
        assert r.status_code == 201, r.text
    return client.get(f"{BASE}/items/{item['id']}", headers=mgr).json()


def event_names(org_id: str) -> list[str]:
    with SessionLocal() as db:
        return [e.name for e in db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == org_id))]


def test_needs_a_token_and_a_permission(client, org):
    assert client.get(f"{BASE}/items").status_code == 401
    _, nobody = org.user("unrelated-role")
    assert client.get(f"{BASE}/items", headers=nobody).status_code == 403


def test_stock_ledger_and_low_stock_events(client, org):
    _, mgr = org.user(MANAGER)
    cat, loc = setup_store(client, mgr)
    second = client.post(f"{BASE}/locations", json={"name": "Studio cupboard"}, headers=mgr).json()
    item = quantity_item(client, mgr, cat, loc, on_hand=10, reorder_level=3, reorder_quantity=20)
    assert (item["on_hand"], item["available"], item["low_stock"]) == (10, 10, False)
    move = {"item_id": item["id"]}
    assert (
        client.post(
            f"{BASE}/movements",
            json=move
            | {"kind": "transfer", "quantity": 4, "from_location_id": loc["id"], "to_location_id": second["id"]},
            headers=mgr,
        ).status_code
        == 201
    )
    too_much = client.post(
        f"{BASE}/movements", json=move | {"kind": "issue", "quantity": 7, "from_location_id": loc["id"]}, headers=mgr
    )
    assert too_much.status_code == 409
    assert too_much.json()["detail"]["code"] == "not_enough_stock"
    no_reason = client.post(
        f"{BASE}/movements",
        json=move | {"kind": "write_off", "quantity": 1, "from_location_id": loc["id"]},
        headers=mgr,
    )
    assert no_reason.json()["detail"]["code"] == "reason_required"
    issued = client.post(
        f"{BASE}/movements", json=move | {"kind": "issue", "quantity": 5, "from_location_id": loc["id"]}, headers=mgr
    )
    assert issued.status_code == 201
    low = client.get(f"{BASE}/low-stock", headers=mgr).json()
    assert low == []  # 5 left against a reorder level of 3
    client.post(
        f"{BASE}/movements",
        json=move
        | {"kind": "write_off", "quantity": 3, "from_location_id": second["id"], "reason": "damaged in transit"},
        headers=mgr,
    )
    low = client.get(f"{BASE}/low-stock", headers=mgr).json()
    assert [(x["item_id"], x["available"]) for x in low] == [(item["id"], 2)]
    client.post(
        f"{BASE}/movements", json=move | {"kind": "receipt", "quantity": 10, "to_location_id": loc["id"]}, headers=mgr
    )
    names = event_names(org.id)
    assert names.count("inventory-equipment.stock.ran-low") == 1
    assert "inventory-equipment.stock.replenished" in names
    assert {
        "inventory-equipment.stock.received",
        "inventory-equipment.stock.issued",
        "inventory-equipment.stock.adjusted",
    } <= set(names)
    ledger = client.get(f"{BASE}/movements", params={"item_id": item["id"]}, headers=mgr).json()
    assert ledger["total"] == 5
    stock = client.get(f"{BASE}/stock", params={"item_id": item["id"]}, headers=mgr).json()
    assert sorted(r["on_hand"] for r in stock) == [1, 11]


def test_full_loan_cycle_of_a_unit(client, org):
    _, mgr = org.user(MANAGER)
    me, borrower = org.user(BORROWER)
    cat, loc = setup_store(client, mgr)
    item = individual_item(client, mgr, cat, loc)
    assert item["available"] == 2
    loan = client.post(
        f"{BASE}/loans",
        json={"lines": [{"item_id": item["id"]}], "due_at": due(3), "purpose": "Short film"},
        headers=borrower,
    )
    assert loan.status_code == 201, loan.text
    loan = loan.json()
    assert loan["status"] == "approved"
    assert loan["borrower_id"] == me
    units = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()
    out = client.post(
        f"{BASE}/loans/{loan['id']}/hand-out",
        json={"lines": [{"line_id": loan["lines"][0]["id"], "unit_id": units[0]["id"], "condition_out": "good"}]},
        headers=mgr,
    )
    assert out.status_code == 200, out.text
    assert out.json()["status"] == "on_loan"
    assert client.get(f"{BASE}/items/{item['id']}", headers=mgr).json()["on_loan"] == 1
    mine = client.get(f"{BASE}/loans", params={"scope": "mine", "open": "true"}, headers=borrower).json()
    assert [x["id"] for x in mine["items"]] == [loan["id"]]
    assert "extend" in mine["items"][0]["can"]
    back = client.post(
        f"{BASE}/loans/{loan['id']}/return",
        json={"lines": [{"line_id": loan["lines"][0]["id"], "condition_in": "damaged", "damage_note": "cracked lens"}]},
        headers=mgr,
    )
    assert back.status_code == 200, back.text
    assert back.json()["status"] == "returned"
    unit = client.get(f"{BASE}/units/{units[0]['id']}", headers=mgr).json()
    assert (unit["status"], unit["condition"]) == ("in_repair", "damaged")
    assert len(unit["recent_movements"]) == 3  # receipt, loan_out, loan_return
    names = event_names(org.id)
    assert {
        "inventory-equipment.loan.approved",
        "inventory-equipment.loan.handed-out",
        "inventory-equipment.loan.returned",
        "inventory-equipment.unit.condition-changed",
    } <= set(names)


def test_approval_flow_and_reservation(client, org):
    _, mgr = org.user(MANAGER)
    approver_id, approver = org.user(APPROVER)
    _, stranger = org.user(APPROVER)
    _, borrower = org.user(BORROWER)
    cat, loc = setup_store(client, mgr, category_rules={"requires_approval": True}, approvers=[approver_id])
    item = individual_item(client, mgr, cat, loc, tags=("V-1",))
    unit = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()[0]
    loan = client.post(
        f"{BASE}/loans",
        json={"lines": [{"item_id": item["id"], "unit_id": unit["id"]}], "due_at": due(2)},
        headers=borrower,
    ).json()
    assert loan["status"] == "requested"
    assert client.post(f"{BASE}/loans/{loan['id']}/approve", headers=stranger).status_code == 404
    queue = client.get(f"{BASE}/loans", params={"scope": "managed", "status": "requested"}, headers=approver).json()
    assert [x["id"] for x in queue["items"]] == [loan["id"]]
    assert set(queue["items"][0]["can"]) >= {"approve", "reject"}
    ok = client.post(f"{BASE}/loans/{loan['id']}/approve", json={"note": "ok"}, headers=approver)
    assert ok.json()["status"] == "approved"
    assert client.get(f"{BASE}/units/{unit['id']}", headers=mgr).json()["status"] == "reserved"
    cancelled = client.post(f"{BASE}/loans/{loan['id']}/cancel", headers=borrower)
    assert cancelled.json()["status"] == "cancelled"
    assert client.get(f"{BASE}/units/{unit['id']}", headers=mgr).json()["status"] == "available"


def test_reject_needs_reason(client, org):
    _, mgr = org.user(MANAGER)
    _, borrower = org.user(BORROWER)
    cat, loc = setup_store(client, mgr, category_rules={"requires_approval": True})
    item = individual_item(client, mgr, cat, loc, tags=("W-1",))
    loan = client.post(
        f"{BASE}/loans", json={"lines": [{"item_id": item["id"]}], "due_at": due(2)}, headers=borrower
    ).json()
    assert client.post(f"{BASE}/loans/{loan['id']}/reject", json={}, headers=mgr).status_code == 422
    r = client.post(f"{BASE}/loans/{loan['id']}/reject", json={"reason": "exam week"}, headers=mgr)
    assert r.json()["status"] == "rejected"


def test_loan_rule_violations(client, org):
    _, mgr = org.user(MANAGER)
    _, borrower = org.user(BORROWER)
    cat, loc = setup_store(client, mgr, category_rules={"max_loan_days": 7, "max_quantity_per_loan": 2})
    cable = quantity_item(client, mgr, cat, loc, on_hand=5)
    paint = client.post(
        f"{BASE}/items",
        json={"name": "Paint", "category_id": cat["id"], "tracking": "quantity", "consumable": True},
        headers=mgr,
    ).json()
    assert paint["loanable"] is False

    def ask(lines, days):
        return client.post(f"{BASE}/loans", json={"lines": lines, "due_at": due(days)}, headers=borrower)

    cases = [
        (ask([{"item_id": cable["id"], "quantity": 1}], 10), 422, "too_long"),
        (ask([{"item_id": cable["id"], "quantity": 1}], -1), 422, "due_in_past"),
        (ask([{"item_id": cable["id"], "quantity": 3}], 2), 422, "too_many_items"),
        (ask([{"item_id": paint["id"]}], 2), 422, "consumable_not_loanable"),
    ]
    for response, status, code in cases:
        assert response.status_code == status, (code, response.text)
        assert response.json()["detail"]["code"] == code
    for _ in range(3):
        assert ask([{"item_id": cable["id"]}], 2).status_code == 201
    limit = ask([{"item_id": cable["id"]}], 2)
    assert limit.json()["detail"]["code"] == "too_many_open_loans"


def test_quantity_loan_hand_out_partial_return_and_lost(client, org):
    _, mgr = org.user(MANAGER)
    borrower_id, _ = org.user(BORROWER)
    cat, loc = setup_store(client, mgr)
    cable = quantity_item(client, mgr, cat, loc, on_hand=5)
    loan = client.post(
        f"{BASE}/loans",
        json={
            "lines": [{"item_id": cable["id"], "quantity": 2}, {"item_id": cable["id"], "quantity": 1}],
            "due_at": due(2),
            "borrower_id": borrower_id,
        },
        headers=mgr,
    ).json()
    l1, l2 = (x["id"] for x in loan["lines"])
    missing = client.post(f"{BASE}/loans/{loan['id']}/hand-out", json={"lines": [{"line_id": l1}]}, headers=mgr)
    assert missing.status_code == 422
    out = client.post(
        f"{BASE}/loans/{loan['id']}/hand-out",
        json={
            "lines": [{"line_id": l1, "from_location_id": loc["id"]}, {"line_id": l2, "from_location_id": loc["id"]}]
        },
        headers=mgr,
    )
    assert out.status_code == 200, out.text
    assert client.get(f"{BASE}/items/{cable['id']}", headers=mgr).json()["available"] == 2
    part = client.post(
        f"{BASE}/loans/{loan['id']}/return", json={"lines": [{"line_id": l1, "condition_in": "good"}]}, headers=mgr
    )
    assert part.json()["status"] == "partially_returned"
    lost = client.post(
        f"{BASE}/loans/{loan['id']}/mark-lost", json={"line_ids": [l2], "reason": "left on bus"}, headers=mgr
    )
    assert lost.json()["status"] == "closed_with_loss"
    assert client.get(f"{BASE}/items/{cable['id']}", headers=mgr).json()["available"] == 4
    assert "inventory-equipment.loan.lost-recorded" in event_names(org.id)


def test_extension_rules(client, org):
    _, mgr = org.user(MANAGER)
    _, borrower = org.user(BORROWER)
    _, other = org.user(BORROWER)
    cat, loc = setup_store(client, mgr)
    item = individual_item(client, mgr, cat, loc, tags=("X-1", "X-2"))
    loan = client.post(
        f"{BASE}/loans", json={"lines": [{"item_id": item["id"]}], "due_at": due(2)}, headers=borrower
    ).json()
    unit = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()[0]
    client.post(
        f"{BASE}/loans/{loan['id']}/hand-out",
        json={"lines": [{"line_id": loan["lines"][0]["id"], "unit_id": unit["id"]}]},
        headers=mgr,
    )
    first = client.post(f"{BASE}/loans/{loan['id']}/extend", json={"due_at": due(5)}, headers=borrower)
    assert first.status_code == 200, first.text
    assert first.json()["extensions"] == 1
    again = client.post(f"{BASE}/loans/{loan['id']}/extend", json={"due_at": due(6)}, headers=borrower)
    assert again.json()["detail"]["code"] == "extension_not_allowed"
    assert client.post(f"{BASE}/loans/{loan['id']}/extend", json={"due_at": due(6)}, headers=other).status_code == 404
    staff = client.post(f"{BASE}/loans/{loan['id']}/extend", json={"due_at": due(9)}, headers=mgr)
    assert staff.json()["extensions"] == 2


def test_sweeps_mark_overdue_and_expire_pickups(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    _, borrower = org.user(BORROWER)
    cat, loc = setup_store(client, mgr)
    item = individual_item(client, mgr, cat, loc, tags=("Y-1", "Y-2"))
    taken = client.post(
        f"{BASE}/loans", json={"lines": [{"item_id": item["id"]}], "due_at": due(1)}, headers=borrower
    ).json()
    unit = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()[0]
    client.post(
        f"{BASE}/loans/{taken['id']}/hand-out",
        json={"lines": [{"line_id": taken["lines"][0]["id"], "unit_id": unit["id"]}]},
        headers=mgr,
    )
    waiting = client.post(
        f"{BASE}/loans", json={"lines": [{"item_id": item["id"]}], "due_at": due(1)}, headers=borrower
    ).json()
    later = NOW + timedelta(days=3)
    monkeypatch.setattr(service, "clock", lambda: later)
    with SessionLocal() as db:
        counts = run_sweeps(db, now=later)
    assert counts["overdue"] >= 1 and counts["pickup_expired"] >= 1
    assert client.get(f"{BASE}/loans/{taken['id']}", headers=borrower).json()["status"] == "overdue"
    assert client.get(f"{BASE}/loans/{waiting['id']}", headers=borrower).json()["status"] == "cancelled"
    overdue = client.get(f"{BASE}/loans", params={"scope": "managed", "status": "overdue"}, headers=mgr).json()
    assert [x["id"] for x in overdue["items"]] == [taken["id"]]
    assert overdue["items"][0]["days_overdue"] == 2
    summary = client.get(f"{BASE}/summary", headers=mgr).json()
    assert summary["loans_overdue"] == 1


def test_unit_status_changes_and_tracking_lock(client, org):
    _, mgr = org.user(MANAGER)
    cat, loc = setup_store(client, mgr)
    item = individual_item(client, mgr, cat, loc, tags=("Z-1",))
    unit = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()[0]
    r = client.put(f"{BASE}/units/{unit['id']}/status", json={"status": "missing", "reason": "audit"}, headers=mgr)
    assert r.json()["status"] == "missing"
    assert "inventory-equipment.unit.status-changed" in event_names(org.id)
    locked = client.patch(f"{BASE}/items/{item['id']}", json={"tracking": "quantity"}, headers=mgr)
    assert locked.status_code == 409
    dup = client.post(f"{BASE}/items/{item['id']}/units", json={"tag": "Z-1", "location_id": loc["id"]}, headers=mgr)
    assert dup.status_code == 409
    busy = client.patch(f"{BASE}/locations/{loc['id']}", json={"active": False}, headers=mgr)
    assert busy.status_code == 200  # the only unit is missing, so the location holds nothing


def test_catalogue_search(client, org):
    _, mgr = org.user(MANAGER)
    _, borrower = org.user(BORROWER)
    cat, loc = setup_store(client, mgr, category="Search")
    a = quantity_item(client, mgr, cat, loc, on_hand=1, name="Long cable", attributes={"length": "10m"}, code="C10")
    quantity_item(client, mgr, cat, loc, on_hand=0, name="Short cable", code="C1")
    found = client.get(f"{BASE}/items", params={"q": "10m"}, headers=borrower).json()
    assert [x["id"] for x in found["items"]] == [a["id"]]
    available = client.get(f"{BASE}/items", params={"available": "true", "category_id": cat["id"]}, headers=borrower)
    assert [x["id"] for x in available.json()["items"]] == [a["id"]]
    assert datetime.fromisoformat(a["created_at"]).tzinfo == UTC


def test_hand_out_with_another_unit_frees_the_reserved_one(client, org):
    _, mgr = org.user(MANAGER)
    approver_id, approver = org.user(APPROVER)
    _, borrower = org.user(BORROWER)
    cat, loc = setup_store(client, mgr, category_rules={"requires_approval": True}, approvers=[approver_id])
    item = individual_item(client, mgr, cat, loc, tags=("R-1", "R-2"))
    pinned, other = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()
    loan = client.post(
        f"{BASE}/loans",
        json={"lines": [{"item_id": item["id"], "unit_id": pinned["id"]}], "due_at": due(2)},
        headers=borrower,
    ).json()
    assert client.post(f"{BASE}/loans/{loan['id']}/approve", headers=approver).status_code == 200
    assert client.get(f"{BASE}/units/{pinned['id']}", headers=mgr).json()["status"] == "reserved"
    out = client.post(
        f"{BASE}/loans/{loan['id']}/hand-out",
        json={"lines": [{"line_id": loan["lines"][0]["id"], "unit_id": other["id"]}]},
        headers=mgr,
    )
    assert out.status_code == 200, out.text
    assert out.json()["lines"][0]["unit_id"] == other["id"]
    assert client.get(f"{BASE}/units/{other['id']}", headers=mgr).json()["status"] == "on_loan"
    assert client.get(f"{BASE}/units/{pinned['id']}", headers=mgr).json()["status"] == "available"
    assert client.get(f"{BASE}/items/{item['id']}", headers=mgr).json()["available"] == 1


def test_return_location_must_be_an_active_location_of_the_organisation(client, org, other_org):
    _, mgr = org.user(MANAGER)
    _, other_mgr = other_org.user(MANAGER)
    cat, loc = setup_store(client, mgr)
    foreign = client.post(f"{BASE}/locations", json={"name": "Their store"}, headers=other_mgr).json()
    item = quantity_item(client, mgr, cat, loc, on_hand=5)

    def lend_one() -> dict:
        loan = client.post(
            f"{BASE}/loans", json={"lines": [{"item_id": item["id"], "quantity": 1}], "due_at": due(2)}, headers=mgr
        ).json()
        r = client.post(
            f"{BASE}/loans/{loan['id']}/hand-out",
            json={"lines": [{"line_id": loan["lines"][0]["id"], "from_location_id": loc["id"]}]},
            headers=mgr,
        )
        assert r.status_code == 200, r.text
        return loan

    for bad in (foreign["id"], "does-not-exist"):
        loan = lend_one()
        r = client.post(
            f"{BASE}/loans/{loan['id']}/return",
            json={"lines": [{"line_id": loan["lines"][0]["id"], "condition_in": "good", "to_location_id": bad}]},
            headers=mgr,
        )
        assert r.status_code == 404, r.text
        assert r.json()["detail"]["code"] == "not_found"
    stock = client.get(f"{BASE}/stock", params={"item_id": item["id"]}, headers=mgr).json()
    assert [(s["location_id"], s["on_hand"]) for s in stock] == [(loc["id"], 3)]
    inactive = client.post(f"{BASE}/locations", json={"name": "Closed", "active": False}, headers=mgr).json()
    loan = lend_one()
    r = client.post(
        f"{BASE}/loans/{loan['id']}/return",
        json={"lines": [{"line_id": loan["lines"][0]["id"], "condition_in": "good", "to_location_id": inactive["id"]}]},
        headers=mgr,
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "location_inactive")


def test_low_stock_event_uses_the_contract_name(client, org):
    _, mgr = org.user(MANAGER)
    cat, loc = setup_store(client, mgr)
    item = quantity_item(client, mgr, cat, loc, on_hand=2, reorder_level=1)
    r = client.post(
        f"{BASE}/movements",
        json={"kind": "issue", "item_id": item["id"], "quantity": 1, "from_location_id": loc["id"]},
        headers=mgr,
    )
    assert r.status_code == 201, r.text
    names = event_names(org.id)
    assert "inventory-equipment.stock.ran-low" in names
    assert not [n for n in names if n.endswith("stock.low")]


def test_unit_detail_shows_only_loans_the_viewer_may_see(client, org):
    _, mgr = org.user(MANAGER)
    approver_id, approver = org.user(APPROVER)
    _, borrower = org.user(BORROWER)
    _, other = org.user(BORROWER)
    cat, loc = setup_store(client, mgr, approvers=[approver_id])
    item = individual_item(client, mgr, cat, loc, tags=("L-1",))
    unit = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()[0]
    line = {"item_id": item["id"], "unit_id": unit["id"]}
    theirs = client.post(f"{BASE}/loans", json={"lines": [line], "due_at": due(1), "purpose": "private"}, headers=other)
    assert theirs.status_code == 201, theirs.text
    client.post(f"{BASE}/loans/{theirs.json()['id']}/cancel", headers=other)
    mine = client.post(f"{BASE}/loans", json={"lines": [line], "due_at": due(1)}, headers=borrower).json()
    assert client.get(f"{BASE}/loans/{theirs.json()['id']}", headers=borrower).status_code == 404

    def seen_by(headers) -> list[str]:
        return [x["id"] for x in client.get(f"{BASE}/units/{unit['id']}", headers=headers).json()["recent_loans"]]

    assert seen_by(borrower) == [mine["id"]]
    assert seen_by(mgr) == [theirs.json()["id"], mine["id"]]  # oldest first, every loan
    assert seen_by(approver) == [theirs.json()["id"], mine["id"]]  # approver of the category sees both


def test_individual_items_refuse_receipt_and_adjustment_movements(client, org):
    _, mgr = org.user(MANAGER)
    cat, loc = setup_store(client, mgr)
    item = individual_item(client, mgr, cat, loc, tags=("C-1",), consumable=True)
    unit = client.get(f"{BASE}/items/{item['id']}/units", headers=mgr).json()[0]
    move = {"item_id": item["id"], "quantity": 1, "unit_ids": [unit["id"]], "reason": "stocktake"}
    for kind in ("receipt", "adjustment"):
        r = client.post(f"{BASE}/movements", json=move | {"kind": kind, "to_location_id": loc["id"]}, headers=mgr)
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "wrong_tracking"), r.text
        assert client.get(f"{BASE}/units/{unit['id']}", headers=mgr).json()["status"] == "available"
    issued = client.post(f"{BASE}/movements", json=move | {"kind": "issue"}, headers=mgr)
    assert issued.status_code == 201, issued.text
    assert client.get(f"{BASE}/units/{unit['id']}", headers=mgr).json()["status"] == "retired"
