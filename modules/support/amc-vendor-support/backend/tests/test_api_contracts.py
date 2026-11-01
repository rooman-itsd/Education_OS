"""Contracts through the HTTP API: record, edit, activate, terminate, renew, covered items and coverage, with their
events and audit entries."""

from datetime import timedelta

from conftest import NOW, VENDOR, audit, contract_body, days, outbox

ASSET = {"module": "asset-management", "entity": "asset", "id": "asset-42"}


def test_record_a_draft_with_a_number_and_defaults(desk):
    first = desk.draft()
    second = desk.draft(owner_id=desk.coordinator_id, value={"amount": "500"})
    assert (first["number"], second["number"]) == ("AMC-000001", "AMC-000002")
    assert (first["status"], first["expiring"], first["expired"]) == ("draft", False, False)
    assert first["owner_id"] == desk.manager_id  # defaults to the caller
    assert second["owner_id"] == desk.coordinator_id
    assert second["value"] == {"amount": "500.00", "currency": "INR"}  # AMC_VENDOR_SUPPORT_DEFAULT_CURRENCY
    assert first["vendor_contacts"][0]["name"] == "Service desk"
    assert audit(desk.org.id, first["id"]) == [("contract.created", None)]


def test_number_prefix_comes_from_settings(desk, monkeypatch):
    monkeypatch.setenv("AMC_VENDOR_SUPPORT_CONTRACT_NUMBER_PREFIX", "AMCX")
    assert desk.draft()["number"].startswith("AMCX-")


def test_numbering_continues_a_sequence_row_that_already_exists(desk):
    """The ON CONFLICT path of next_number: the row was created first, as by a concurrent first contract."""
    from eos_amc_vendor_support.infrastructure.models import NumberSequence
    from eos_core.db import SessionLocal

    with SessionLocal() as db:
        db.add(NumberSequence(organisation_id=desk.org.id, kind="contract", last_number=5))
        db.commit()
    assert desk.draft()["number"] == "AMC-000006"


TOO_BIG = {
    "response_hours": 8761,
    "resolution_hours": 10**11,
    "preventive_visits_per_year": 367,
    "value": {"amount": "1" * 13, "currency": "INR"},
    "purchase_order_reference": {"module": "procurement", "entity": "purchase-order", "id": "p" * 101},
}


def test_values_too_big_for_their_columns_are_a_422_not_a_500(desk):
    """Bounds the contract leaves open are those of the columns: Integer, Numeric(14, 2), String(60/60/100)."""
    draft = desk.draft()
    for field, value in TOO_BIG.items():
        assert desk.post("/contracts", contract_body(**{field: value})).status_code == 422, field
        assert desk.patch(f"/contracts/{draft['id']}", {field: value}).status_code == 422, field
    for field in ("module", "entity"):
        too_long = {**ASSET, field: "m" * 61}
        assert (
            desk.post(
                f"/contracts/{draft['id']}/covered-items", {"description": "Lift", "reference": too_long}
            ).status_code
            == 422
        )
    largest = desk.draft(
        response_hours=8760,
        resolution_hours=8760,
        preventive_visits_per_year=366,
        value={"amount": "999999999999.99", "currency": "INR"},
    )
    assert (largest["response_hours"], largest["value"]["amount"]) == (8760, "999999999999.99")


def test_record_refuses_bad_values(desk):
    bad = desk.post("/contracts", contract_body(end_date="2026-04-01"))
    assert (bad.status_code, bad.json()["detail"]["code"]) == (422, "end_before_start")
    assert desk.post("/contracts", contract_body(coverage_type="full")).status_code == 422
    assert desk.post("/contracts", contract_body(vendor_id="not-a-uuid")).status_code == 422
    assert desk.post("/contracts", contract_body(value={"amount": "12.345"})).status_code == 422
    assert desk.post("/contracts", contract_body(unknown=1)).status_code == 422


def test_get_one_with_items_and_counts(desk):
    contract = desk.active()
    desk.item(contract["id"], reference=ASSET)
    detail = desk.ok(desk.get(f"/contracts/{contract['id']}", desk.viewer))
    assert detail["covered_items"][0]["reference"] == ASSET
    assert detail["engagement_counts"] == {"open": 0, "resolved": 0, "outside_terms": 0}
    assert desk.get("/contracts/00000000-0000-4000-8000-000000000000").status_code == 404


def test_draft_is_edited_freely_active_only_owner_contacts_and_notice(desk):
    draft = desk.draft()
    edited = desk.ok(desk.patch(f"/contracts/{draft['id']}", {"title": "Lift AMC", "end_date": "2027-06-30"}))
    assert (edited["title"], edited["end_date"]) == ("Lift AMC", "2027-06-30")
    bad = desk.patch(f"/contracts/{draft['id']}", {"end_date": "2026-03-01"})
    assert (bad.status_code, bad.json()["detail"]["code"]) == (422, "end_before_start")
    active = desk.ok(desk.post(f"/contracts/{draft['id']}/activate", {}))
    ok = desk.ok(desk.patch(f"/contracts/{active['id']}", {"renewal_notice_days": 90, "owner_id": desk.viewer_id}))
    assert (ok["renewal_notice_days"], ok["owner_id"]) == (90, desk.viewer_id)
    locked = desk.patch(f"/contracts/{active['id']}", {"end_date": "2028-01-01"})
    assert (locked.status_code, locked.json()["detail"]["code"]) == (409, "field_not_editable")


def test_purchase_order_reference_can_be_cleared_on_a_draft(desk):
    draft = desk.draft(purchase_order_reference={"module": "procurement", "entity": "purchase-order", "id": "po-1"})
    cleared = desk.ok(desk.patch(f"/contracts/{draft['id']}", {"purchase_order_reference": None}))
    assert cleared["purchase_order_reference"] is None


def test_activate_publishes_contract_activated_with_covered_references(desk):
    draft = desk.draft()
    desk.item(draft["id"], reference=ASSET)
    desk.item(draft["id"], description="Generator, no reference")
    active = desk.ok(desk.post(f"/contracts/{draft['id']}/activate", {}))
    assert (active["status"], active["activated_at"]) == ("active", "2026-11-01T09:00:00+00:00")
    event = outbox("amc-vendor-support.contract.activated", desk.org.id)[-1]
    assert event == {
        "organisation_id": desk.org.id,
        "contract_id": draft["id"],
        "number": draft["number"],
        "vendor_id": VENDOR,
        "coverage_type": "comprehensive",
        "start_date": "2026-04-01",
        "end_date": "2027-03-31",
        "renewed_from_id": None,
        "covered_references": [ASSET],
    }
    again = desk.post(f"/contracts/{draft['id']}/activate", {})
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "not_draft")


def test_terminate_an_active_contract(desk):
    contract = desk.active()
    body = {"reason": "Vendor closed down", "effective_date": "2026-12-31"}
    assert desk.post(f"/contracts/{desk.draft()['id']}/terminate", body).status_code == 409
    done = desk.ok(desk.post(f"/contracts/{contract['id']}/terminate", body))
    assert (done["status"], done["termination_reason"], done["termination_effective_date"]) == (
        "terminated",
        "Vendor closed down",
        "2026-12-31",
    )
    event = outbox("amc-vendor-support.contract.terminated", desk.org.id)[-1]
    assert set(event) == {"organisation_id", "contract_id", "number", "vendor_id", "effective_date", "terminated_at"}
    assert event["effective_date"] == "2026-12-31"
    assert ("contract.terminated", "Vendor closed down") in audit(desk.org.id, contract["id"])
    assert desk.patch(f"/contracts/{contract['id']}", {"owner_id": desk.viewer_id}).status_code == 409


def test_renew_creates_a_draft_successor_and_activating_it_renews_the_original(desk):
    original = desk.active(end_date="2027-03-31")
    desk.item(original["id"], reference=ASSET)
    assert desk.post(f"/contracts/{original['id']}/renew", {"end_date": "2027-04-01"}).status_code == 422
    successor = desk.ok(desk.post(f"/contracts/{original['id']}/renew", {"end_date": "2028-03-31"}))
    assert (successor["status"], successor["start_date"], successor["renewed_from_id"]) == (
        "draft",
        "2027-04-01",
        original["id"],
    )
    assert successor["value"] == {"amount": "120000.00", "currency": "INR"}  # copied
    assert successor["response_hours"] == 4
    assert desk.ok(desk.get(f"/contracts/{successor['id']}"))["covered_items"][0]["reference"] == ASSET
    assert desk.ok(desk.get(f"/contracts/{original['id']}"))["renewed_to_id"] == successor["id"]
    twice = desk.post(f"/contracts/{original['id']}/renew", {"end_date": "2028-03-31"})
    assert (twice.status_code, twice.json()["detail"]["code"]) == (409, "successor_exists")

    desk.ok(desk.post(f"/contracts/{successor['id']}/activate", {}))
    assert desk.ok(desk.get(f"/contracts/{original['id']}"))["status"] == "renewed"
    renewed = outbox("amc-vendor-support.contract.renewed", desk.org.id)[-1]
    assert (renewed["contract_id"], renewed["successor_id"], renewed["successor_number"]) == (
        original["id"],
        successor["id"],
        successor["number"],
    )
    activated = outbox("amc-vendor-support.contract.activated", desk.org.id)[-1]
    assert (activated["contract_id"], activated["renewed_from_id"]) == (successor["id"], original["id"])


def test_a_renewal_cannot_be_activated_once_the_original_is_terminated(desk):
    original = desk.active()
    successor = desk.ok(desk.post(f"/contracts/{original['id']}/renew", {"end_date": "2028-03-31"}))
    desk.ok(desk.post(f"/contracts/{original['id']}/terminate", {"reason": "Ended early", "effective_date": days(1)}))
    refused = desk.post(f"/contracts/{successor['id']}/activate", {})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "predecessor_not_active")


def test_a_contract_ending_on_the_last_possible_day_cannot_be_renewed(desk):
    """The default start (end_date + 1 day) does not exist, so the renewal is a 422, not an overflow."""
    original = desk.active(start_date="9999-01-01", end_date="9999-12-31")
    refused = desk.post(f"/contracts/{original['id']}/renew", {"end_date": "9999-12-31"})
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "end_before_start")


def test_renew_with_a_new_value_and_start(desk):
    original = desk.active()
    body = {"start_date": "2027-05-01", "end_date": "2028-04-30", "value": {"amount": "130000", "currency": "INR"}}
    successor = desk.ok(desk.post(f"/contracts/{original['id']}/renew", body))
    assert (successor["start_date"], successor["value"]["amount"]) == ("2027-05-01", "130000.00")


def test_covered_items_add_duplicate_remove(desk):
    contract = desk.active()
    item = desk.item(contract["id"], reference=ASSET)
    dup = desk.post(f"/contracts/{contract['id']}/covered-items", {"description": "Again", "reference": ASSET})
    assert (dup.status_code, dup.json()["detail"]["code"]) == (409, "already_covered")
    assert desk.delete(f"/contracts/{contract['id']}/covered-items/{item['id']}").status_code == 204
    assert desk.delete(f"/contracts/{contract['id']}/covered-items/{item['id']}").status_code == 404
    # The clock is frozen, so entries share occurred_at; compare without relying on their order.
    assert sorted(audit(desk.org.id, item["id"])) == [("covered_item.added", None), ("covered_item.removed", None)]


def test_covered_items_of_a_closed_contract_do_not_change(desk):
    contract = desk.active()
    item = desk.item(contract["id"])
    desk.ok(desk.post(f"/contracts/{contract['id']}/terminate", {"reason": "Ended", "effective_date": days(0)}))
    assert desk.post(f"/contracts/{contract['id']}/covered-items", {"description": "New"}).status_code == 409
    assert desk.delete(f"/contracts/{contract['id']}/covered-items/{item['id']}").status_code == 409


def test_coverage_finds_active_contracts_covering_a_record(desk, clock):
    covering = desk.active(end_date=days(100))
    desk.item(covering["id"], reference=ASSET)
    draft = desk.draft()
    desk.item(draft["id"], reference=ASSET)  # drafts do not cover yet
    ending = desk.active(start_date=days(-300), end_date=days(5))
    desk.item(ending["id"], reference=ASSET)
    query = "/coverage?module=asset-management&entity=asset&id=asset-42"
    found = desk.ok(desk.get(query, desk.viewer))
    assert [c["id"] for c in found] == [ending["id"], covering["id"]]  # soonest end first
    clock.set(NOW + timedelta(days=10))  # ending is now expired
    assert [c["id"] for c in desk.ok(desk.get(query))] == [covering["id"]]
    assert [c["id"] for c in desk.ok(desk.get(query + "&include_expired=true"))] == [ending["id"], covering["id"]]
    assert desk.ok(desk.get("/coverage?module=asset-management&entity=asset&id=other")) == []


def test_list_filters_and_order(desk):
    soon = desk.active(title="Generator AMC", start_date=days(-200), end_date=days(20))
    later = desk.active(title="Chiller AMC", start_date=days(-30), end_date=days(300))
    past = desk.active(title="UPS AMC", start_date=days(-400), end_date=days(-2))
    draft = desk.draft(title="Server AMC", owner_id=desk.coordinator_id, end_date=days(40), start_date=days(1))

    def ids(query: str) -> list[str]:
        return [c["id"] for c in desk.ok(desk.get(f"/contracts{query}"))["items"]]

    mine = {soon["id"], later["id"], past["id"], draft["id"]}
    assert [i for i in ids("") if i in mine] == [past["id"], soon["id"], draft["id"], later["id"]]
    assert set(ids("?status=draft")) & mine == {draft["id"]}
    assert set(ids("?expiring=true")) & mine == {soon["id"]}
    assert set(ids("?expired=true")) & mine == {past["id"]}
    assert set(ids("?q=chiller")) & mine == {later["id"]}
    assert set(ids(f"?q={soon['number']}")) & mine == {soon["id"]}
    assert set(ids(f"?owner={desk.coordinator_id}")) & mine == {draft["id"]}
    assert desk.get("/contracts?status=lost").status_code == 422


def test_list_paginates_with_a_cursor(desk):
    for _ in range(3):
        desk.draft()
    first = desk.ok(desk.get("/contracts?limit=2"))
    assert len(first["items"]) == 2 and first["next_cursor"]
    second = desk.ok(desk.get(f"/contracts?limit=2&cursor={first['next_cursor']}"))
    assert {c["id"] for c in first["items"]}.isdisjoint({c["id"] for c in second["items"]})
