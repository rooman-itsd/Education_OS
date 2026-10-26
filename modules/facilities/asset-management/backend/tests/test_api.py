"""Integration tests through the HTTP API, against a throwaway SQLite database (see conftest)."""

from datetime import timedelta

from conftest import BASE, NOW
from eos_asset_management.application import service
from eos_asset_management.application.jobs import run_sweeps
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from sqlalchemy import select, text

MANAGER = "asset-management-manager"
FINANCE = "asset-management-finance"
CUSTODIAN = "asset-management-custodian"
VERIFIER = "asset-management-verifier"

STRAIGHT_LINE = {"method": "straight_line", "useful_life_months": 60, "residual_percent": 5}


def events(org_id: str, name: str | None = None) -> list[OutboxEvent]:
    with SessionLocal() as db:
        q = select(OutboxEvent).where(OutboxEvent.organisation_id == org_id).order_by(text("rowid"))  # insertion order
        found = list(db.scalars(q))
    return [e for e in found if name is None or e.name == name]


def category(client, mgr, name="IT equipment", **fields) -> dict:
    r = client.post(f"{BASE}/categories", json={"name": name} | fields, headers=mgr)
    assert r.status_code == 201, r.text
    return r.json()


def inr(amount: str) -> dict:
    return {"amount": amount, "currency": "INR"}


def register(client, mgr, cat, *, cost="60000.00", in_service="2026-08-01", **fields) -> dict:
    body = {
        "name": "Laptop",
        "category_id": cat["id"],
        "acquisition": {"date": in_service, "cost": inr(cost), "supplier_name": "Acme"},
    } | fields
    r = client.post(f"{BASE}/assets", json=body, headers=mgr)
    assert r.status_code == 201, r.text
    return r.json()


def post(client, who, path, body=None, expect=200) -> dict:
    r = client.post(f"{BASE}{path}", json=body, headers=who)
    assert r.status_code == expect, r.text
    return r.json() if r.content else {}


# ---------------------------------------------------------------- categories


def test_categories_validate_depreciation_and_refuse_nulls(client, org):
    _, mgr = org.user(MANAGER)
    _, cust = org.user(CUSTODIAN)
    cat = category(client, mgr, code="IT", depreciation=STRAIGHT_LINE, verification_interval_months=6)
    assert cat["depreciation"] == STRAIGHT_LINE and cat["asset_count"] == 0
    assert client.post(f"{BASE}/categories", json={"name": "IT equipment"}, headers=mgr).status_code == 409
    assert client.post(f"{BASE}/categories", json={"name": "Vans"}, headers=cust).status_code == 403
    bad = client.post(
        f"{BASE}/categories", json={"name": "Vans", "depreciation": {"method": "straight_line"}}, headers=mgr
    )
    assert bad.status_code == 422 and bad.json()["detail"]["code"] == "invalid_depreciation"
    assert client.patch(f"{BASE}/categories/{cat['id']}", json={"name": None}, headers=mgr).status_code == 422
    cleared = client.patch(f"{BASE}/categories/{cat['id']}", json={"code": None}, headers=mgr).json()
    assert cleared["code"] is None
    assert [c["name"] for c in client.get(f"{BASE}/categories", headers=cust).json()] == ["IT equipment"]


# ---------------------------------------------------------------- the register


def test_register_generates_tags_and_values_the_asset(client, org):
    _, mgr = org.user(MANAGER)
    cat = category(client, mgr, code="IT", depreciation=STRAIGHT_LINE)
    a = register(client, mgr, cat, serial_number="SN-1")
    assert a["tag"] == "AST-IT-00001"
    assert a["status"] == "in_service" and a["condition"] == "good"
    assert a["in_service_date"] == "2026-08-01"  # from the acquisition date
    assert a["acquisition"]["cost"] == inr("60000.00") and a["acquisition"]["supplier_name"] == "Acme"
    assert a["book_value"] == inr("60000.00") and a["accumulated_depreciation"] == inr("0.00")
    assert a["effective_depreciation"]["method"] == "straight_line"
    assert a["next_verification_due"] == "2027-08-01"  # 12 months by default
    b = register(client, mgr, cat)
    assert b["tag"] == "AST-IT-00002"
    own = register(client, mgr, cat, tag="LAB-7")
    assert own["tag"] == "LAB-7"
    clash = client.post(f"{BASE}/assets", json={"name": "x", "category_id": cat["id"], "tag": "LAB-7"}, headers=mgr)
    assert clash.status_code == 409
    usd = client.post(
        f"{BASE}/assets",
        json={"name": "x", "category_id": cat["id"], "acquisition": {"cost": {"amount": "5", "currency": "USD"}}},
        headers=mgr,
    )
    assert usd.status_code == 422 and usd.json()["detail"]["code"] == "currency_mismatch"
    registered = events(org.id, "asset-management.asset.registered")[0].payload
    assert registered["tag"] == "AST-IT-00001" and registered["cost"] == inr("60000.00")
    assert client.get(f"{BASE}/categories", headers=mgr).json()[0]["asset_count"] == 3


def test_custodians_see_only_their_assets(client, org):
    _, mgr = org.user(MANAGER)
    cust_id, cust = org.user(CUSTODIAN)
    cat = category(client, mgr)
    mine = register(client, mgr, cat, custodian_id=cust_id)
    other = register(client, mgr, cat)
    listed = client.get(f"{BASE}/assets", headers=cust).json()
    assert [x["id"] for x in listed["items"]] == [mine["id"]]
    assert client.get(f"{BASE}/assets/{other['id']}", headers=cust).status_code == 404
    assert client.get(f"{BASE}/assets?q=laptop&status=in_service", headers=mgr).json()["total"] == 2
    assert client.get(f"{BASE}/assets?status=bogus", headers=mgr).status_code == 422
    assert client.get(f"{BASE}/summary", headers=cust).status_code == 403


def test_edit_status_and_transfers(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    new_custodian, cust = org.user(CUSTODIAN)
    cat = category(client, mgr)
    a = register(client, mgr, cat, location="Lab 1")
    edited = client.patch(
        f"{BASE}/assets/{a['id']}", json={"make": "Dell", "warranty_until": "2026-11-01"}, headers=mgr
    )
    assert edited.json()["make"] == "Dell"
    assert events(org.id, "asset-management.asset.updated")[0].payload["changed"] == ["make", "warranty_until"]
    assert client.patch(f"{BASE}/assets/{a['id']}", json={"name": None}, headers=mgr).status_code == 422
    assert client.patch(f"{BASE}/assets/{a['id']}", json={"location": "x"}, headers=mgr).status_code == 422

    put = client.put(f"{BASE}/assets/{a['id']}/status", json={"status": "in_repair", "reason": "Screen"}, headers=mgr)
    assert put.json()["status"] == "in_repair"
    changed = events(org.id, "asset-management.asset.status-changed")[0].payload
    assert (changed["from"], changed["to"]) == ("in_service", "in_repair")

    url = f"{BASE}/assets/{a['id']}/transfers"
    moved = post(
        client,
        mgr,
        f"/assets/{a['id']}/transfers",
        {"location": "Lab 2", "custodian_id": new_custodian, "reason": "New lab"},
        201,
    )
    assert moved["from"] == {"location": "Lab 1", "custodian_id": None}
    assert moved["to"] == {"location": "Lab 2", "custodian_id": new_custodian}
    assert moved["source"] == "manual"
    monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(hours=1))  # history is newest first
    post(client, mgr, f"/assets/{a['id']}/transfers", {"location": "Lab 3", "reason": "Again"}, 201)
    history = client.get(url, headers=mgr).json()
    assert [h["to"].get("location") for h in history] == ["Lab 3", "Lab 2"]
    assert post(client, mgr, f"/assets/{a['id']}/transfers", {"location": "Lab 3", "reason": "Same"}, 422)
    assert client.post(url, json={"reason": "nothing"}, headers=mgr).status_code == 422
    # the new custodian now sees it
    assert client.get(f"{BASE}/assets/{a['id']}", headers=cust).json()["location"] == "Lab 3"


# ---------------------------------------------------------------- verification


def test_verification_due_cycle_and_overdue_sweep(client, org):
    _, mgr = org.user(MANAGER)
    _, verifier = org.user(VERIFIER)
    cat = category(client, mgr, code="FN")
    overdue = register(client, mgr, cat, name="Projector", in_service="2025-09-01", location="Hall")
    soon = register(client, mgr, cat, name="Printer", in_service="2025-11-01", location="Office")
    fresh = register(client, mgr, cat, name="Desk", in_service="2026-10-01", location="Room 4")

    due = client.get(f"{BASE}/verifications/due", headers=mgr).json()
    assert (due["within_days"], due["overdue_count"], due["due_soon_count"]) == (30, 1, 1)
    assert [(x["tag"], x["overdue"]) for x in due["assets"]] == [(overdue["tag"], True), (soon["tag"], False)]

    with SessionLocal() as db:
        assert run_sweeps(db, today=NOW.date())["verification_overdue"] >= 1
    with SessionLocal() as db:
        run_sweeps(db, today=NOW.date())  # published once per due date
    flagged = [e.payload["asset_id"] for e in events(org.id, "asset-management.asset.verification-overdue")]
    assert flagged == [overdue["id"]]

    cycle = post(
        client,
        mgr,
        "/verification-cycles",
        {"name": "Q4 audit", "due_on": "2026-10-31", "verifier_user_ids": ["v1"]},
        201,
    )
    assert cycle["status"] == "planned"
    assert (
        client.post(
            f"{BASE}/verification-cycles", json={"name": "x", "due_on": "2026-10-31"}, headers=verifier
        ).status_code
        == 403
    )
    started = post(client, mgr, f"/verification-cycles/{cycle['id']}/start")
    assert started["status"] == "in_progress" and started["counts"]["pending"] == 3
    assert events(org.id, "asset-management.verification-cycle.started")[0].payload["asset_count"] == 3
    assert post(client, mgr, f"/verification-cycles/{cycle['id']}/start", expect=409)

    lines_url = f"/verification-cycles/{cycle['id']}/lines"
    assert post(client, verifier, lines_url, [{"tag": soon["tag"], "result": "relocated"}], 422)
    assert post(client, verifier, lines_url, [{"tag": "NOPE", "result": "found"}], 422)
    done = post(
        client,
        verifier,
        lines_url,
        [
            {"tag": overdue["tag"], "result": "found", "condition": "fair"},
            {"asset_id": soon["id"], "result": "relocated", "observed_location": "Store room"},
        ],
    )
    assert [x["result"] for x in done] == ["found", "relocated"]
    assert client.get(f"{BASE}{lines_url}?result=pending", headers=verifier).json()["total"] == 1

    refused = post(client, mgr, f"/verification-cycles/{cycle['id']}/close", {}, 409)
    assert refused["detail"]["code"] == "lines_pending"
    closed = post(client, mgr, f"/verification-cycles/{cycle['id']}/close", {"close_with_pending": True})
    assert closed["status"] == "closed"
    assert closed["counts"] == {"total": 3, "pending": 0, "found": 1, "missing": 1, "damaged": 0, "relocated": 1}

    seen = client.get(f"{BASE}/assets/{overdue['id']}", headers=mgr).json()
    assert seen["last_verified_at"] == "2026-10-12" and seen["condition"] == "fair"
    assert seen["next_verification_due"] == "2027-10-12"
    moved = client.get(f"{BASE}/assets/{soon['id']}", headers=mgr).json()
    assert moved["location"] == "Store room"
    assert client.get(f"{BASE}/assets/{soon['id']}/transfers", headers=mgr).json()[0]["source"] == "verification"
    assert client.get(f"{BASE}/assets/{fresh['id']}", headers=mgr).json()["status"] == "missing"
    summary = events(org.id, "asset-management.verification-cycle.closed")[0].payload
    assert summary["missing_asset_ids"] == [fresh["id"]]
    assert client.get(f"{BASE}/verifications/due", headers=mgr).json()["overdue_count"] == 0


# ---------------------------------------------------------------- depreciation


def test_depreciation_runs_draft_post_and_lock(client, org):
    _, mgr = org.user(MANAGER)
    _, fin = org.user(FINANCE)
    cat = category(client, mgr, depreciation=STRAIGHT_LINE)
    land = category(client, mgr, name="Land", depreciation={"method": "none"})
    a = register(client, mgr, cat)  # 60000 from 1 Aug 2026: 950 a month
    register(client, mgr, land, cost="900000.00")

    assert client.post(f"{BASE}/depreciation-runs", json={"period_end": "2026-09-30"}, headers=mgr).status_code == 403
    assert post(client, fin, "/depreciation-runs", {"period_end": "2026-09-15"}, 422)
    run = post(client, fin, "/depreciation-runs", {"period_end": "2026-09-30"}, 202)
    assert run["status"] == "draft" and run["asset_count"] == 1
    assert run["total"] == inr("1900.00")  # August and September; land is not depreciated
    assert run["by_category"] == [{"category_id": cat["id"], "amount": inr("1900.00"), "asset_count": 1}]
    again = post(client, fin, "/depreciation-runs", {"period_end": "2026-09-30"}, 202)  # replaces the draft
    assert [r["id"] for r in client.get(f"{BASE}/depreciation-runs", headers=fin).json()] == [again["id"]]
    lines = client.get(f"{BASE}/depreciation-runs/{again['id']}/lines", headers=fin).json()
    assert lines["items"][0]["closing_book_value"] == inr("58100.00")

    posted = post(client, fin, f"/depreciation-runs/{again['id']}/post")
    assert posted["status"] == "posted" and posted["posted_at"]
    assert events(org.id, "asset-management.depreciation-run.posted")[0].payload["total"] == inr("1900.00")
    asset = client.get(f"{BASE}/assets/{a['id']}", headers=mgr).json()
    assert asset["book_value"] == inr("58100.00") and asset["accumulated_depreciation"] == inr("1900.00")
    assert client.delete(f"{BASE}/depreciation-runs/{again['id']}", headers=fin).status_code == 409
    assert (
        post(client, fin, "/depreciation-runs", {"period_end": "2026-09-30"}, 409)["detail"]["code"] == "period_posted"
    )

    schedule = client.get(f"{BASE}/assets/{a['id']}/depreciation", headers=fin).json()
    assert schedule["residual_value"] == inr("3000.00")
    assert [p["amount"] for p in schedule["posted"]] == [inr("1900.00")]
    assert schedule["projected"][0] == {
        "period_end": "2026-10-31",
        "amount": inr("950.00"),
        "book_value_after": inr("57150.00"),
    }
    assert schedule["projected"][-1]["book_value_after"] == inr("3000.00")

    october = post(client, fin, "/depreciation-runs", {"period_end": "2026-10-31"}, 202)
    november = post(client, fin, "/depreciation-runs", {"period_end": "2026-11-30"}, 202)
    assert october["period_start"] == "2026-10-01" and october["total"] == inr("950.00")
    assert (
        post(client, fin, f"/depreciation-runs/{november['id']}/post", expect=409)["detail"]["code"]
        == "earlier_not_posted"
    )
    assert client.delete(f"{BASE}/depreciation-runs/{november['id']}", headers=fin).status_code == 204
    post(client, fin, f"/depreciation-runs/{october['id']}/post")


# ---------------------------------------------------------------- disposal


def test_disposal_request_decide_and_complete(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    _, fin = org.user(FINANCE)
    cust_id, cust = org.user(CUSTODIAN)
    cat = category(client, mgr, depreciation=STRAIGHT_LINE)
    a = register(client, mgr, cat, custodian_id=cust_id, inventory_unit_id="8f0c2c3e-0000-4000-8000-000000000001")
    other = register(client, mgr, cat)
    post(
        client,
        fin,
        f"/depreciation-runs/{post(client, fin, '/depreciation-runs', {'period_end': '2026-09-30'}, 202)['id']}/post",
    )

    # a custodian may only ask for assets in their care
    assert post(client, cust, "/disposals", {"asset_id": other["id"], "method": "scrap", "reason": "x"}, 404)
    req = post(
        client,
        cust,
        "/disposals",
        {"asset_id": a["id"], "method": "sale", "reason": "Obsolete", "expected_proceeds": inr("40000")},
        201,
    )
    assert req["status"] == "requested" and req["asset_tag"] == a["tag"]
    assert client.get(f"{BASE}/assets/{a['id']}", headers=mgr).json()["status"] == "disposal_pending"
    assert (
        client.put(f"{BASE}/assets/{a['id']}/status", json={"status": "idle", "reason": "x"}, headers=mgr).status_code
        == 409
    )
    assert post(client, mgr, "/disposals", {"asset_id": a["id"], "method": "scrap", "reason": "x"}, 409)
    assert client.get(f"{BASE}/disposals", headers=cust).json()["total"] == 1
    assert (
        post(client, mgr, f"/disposals/{req['id']}/complete", {"disposed_on": "2026-10-15"}, 409)["detail"]["code"]
        == "not_approved"
    )

    # rejected: the asset goes back to how it was
    rejected = post(client, fin, f"/disposals/{req['id']}/reject", {"reason": "Still useful"})
    assert rejected["status"] == "rejected" and rejected["decision_note"] == "Still useful"
    assert client.get(f"{BASE}/assets/{a['id']}", headers=mgr).json()["status"] == "in_service"

    # withdrawn by the requester
    again = post(client, mgr, "/disposals", {"asset_id": a["id"], "method": "sale", "reason": "Upgrade"}, 201)
    assert post(client, cust, f"/disposals/{again['id']}/cancel", expect=404)  # not the requester's
    assert post(client, mgr, f"/disposals/{again['id']}/cancel")["status"] == "cancelled"

    # approved by finance, then carried out
    final = post(client, mgr, "/disposals", {"asset_id": a["id"], "method": "sale", "reason": "Upgrade"}, 201)
    assert post(client, fin, f"/disposals/{final['id']}/approve", {"note": "OK"})["status"] == "approved"
    done = post(
        client,
        mgr,
        f"/disposals/{final['id']}/complete",
        {"disposed_on": "2026-10-15", "proceeds": inr("50000.00"), "recipient": "Staff sale"},
    )
    assert done["status"] == "completed"
    assert done["book_value_at_disposal"] == inr("57150.00")  # October taken on disposal
    assert done["gain_or_loss"] == inr("-7150.00")
    gone = client.get(f"{BASE}/assets/{a['id']}", headers=mgr).json()
    assert gone["status"] == "disposed" and gone["disposed_on"] == "2026-10-15"
    assert gone["next_verification_due"] is None
    assert client.patch(f"{BASE}/assets/{a['id']}", json={"make": "x"}, headers=mgr).status_code == 409
    assert (
        client.post(
            f"{BASE}/assets/{a['id']}/transfers", json={"location": "x", "reason": "x"}, headers=mgr
        ).status_code
        == 409
    )
    disposed = events(org.id, "asset-management.asset.disposed")[0].payload
    assert disposed["gain_or_loss"] == inr("-7150.00") and disposed["inventory_unit_id"].startswith("8f0c")
    names = [e.name.split(".", 1)[1] for e in events(org.id) if "disposal" in e.name]
    assert names == [
        "disposal.requested",
        "disposal.rejected",
        "disposal.requested",
        "disposal.cancelled",
        "disposal.requested",
        "disposal.approved",
    ]
    schedule = client.get(f"{BASE}/assets/{a['id']}/depreciation", headers=fin).json()
    assert [p["amount"] for p in schedule["posted"]] == [inr("1900.00"), inr("950.00")]
    assert schedule["projected"] == []


def test_requester_cannot_decide_their_own_disposal(client, org):
    _, mgr = org.user(MANAGER)
    both_id, both = org.user(MANAGER, FINANCE)
    cat = category(client, mgr)
    a = register(client, mgr, cat)
    req = post(client, both, "/disposals", {"asset_id": a["id"], "method": "scrap", "reason": "Broken"}, 201)
    assert post(client, both, f"/disposals/{req['id']}/approve", expect=409)["detail"]["code"] == "own_request"
    assert req["requested_by"] == both_id


def test_summary_counts(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    _, fin = org.user(FINANCE)
    cat = category(client, mgr, depreciation=STRAIGHT_LINE)
    register(client, mgr, cat, in_service="2025-09-01", warranty_until="2026-10-30")
    b = register(client, mgr, cat, cost="1000.00", in_service="2026-10-01")
    post(client, mgr, "/disposals", {"asset_id": b["id"], "method": "scrap", "reason": "x"}, 201)
    post(client, mgr, "/verification-cycles", {"name": "Audit", "due_on": "2026-12-01"}, 201)
    s = client.get(f"{BASE}/summary", headers=fin).json()
    assert s["assets_total"] == 2
    assert s["by_status"] == {"in_service": 1, "disposal_pending": 1}
    assert s["verification_overdue"] == 1 and s["verification_due_soon"] == 0
    assert s["open_cycles"] == 1 and s["disposals_awaiting_approval"] == 1
    assert s["warranties_expiring_30_days"] == 1
    assert s["total_cost"] == inr("61000.00") and s["total_book_value"] == inr("61000.00")
    monkeypatch.setattr(service, "clock", lambda: NOW + timedelta(days=60))
    assert client.get(f"{BASE}/summary", headers=fin).json()["warranties_expiring_30_days"] == 0


def test_a_generated_tag_that_collides_is_retried_once(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    cat = category(client, mgr, code="IT")
    first = register(client, mgr, cat)
    real = service._generate_tag
    handed = iter([first["tag"]])  # a concurrent registration took this number a moment ago

    def colliding(db, organisation_id, settings, code):
        return next(handed, None) or real(db, organisation_id, settings, code)

    monkeypatch.setattr(service, "_generate_tag", colliding)
    second = register(client, mgr, cat)
    assert second["tag"] == "AST-IT-00002"
