"""Engagements through the HTTP API: raise against an active contract, move through the statuses, within_terms
worked out when read, and the filters."""

from datetime import timedelta

from conftest import NOW, audit, days

LATER = (NOW + timedelta(hours=3)).isoformat()
TOO_LATE = (NOW + timedelta(hours=30)).isoformat()


def test_raise_an_engagement_with_a_number(desk):
    contract = desk.active()
    item = desk.item(contract["id"])
    ref = {"module": "maintenance", "entity": "ticket", "id": "mt-7"}
    first = desk.engagement(contract["id"], covered_item_id=item["id"], references=[ref], vendor_call_reference="V-99")
    second = desk.engagement(contract["id"], kind="preventive_visit", description="Quarterly service")
    assert (first["number"], second["number"]) == ("AVS-000001", "AVS-000002")
    assert (first["status"], first["raised_by"], first["reported_at"]) == (
        "open",
        desk.coordinator_id,
        "2026-11-01T09:00:00+00:00",
    )
    assert (first["references"], first["vendor_call_reference"], first["within_terms"]) == ([ref], "V-99", None)
    assert audit(desk.org.id, first["id"]) == [("engagement.raised", None)]


def test_raise_refused_on_a_draft_expired_or_terminated_contract(desk, clock):
    def raise_on(contract_id: str):
        body = {"contract_id": contract_id, "kind": "breakdown_call", "description": "Broken"}
        return desk.post("/engagements", body, desk.coordinator)

    draft = desk.draft()
    assert (raise_on(draft["id"]).status_code, raise_on(draft["id"]).json()["detail"]["code"]) == (
        409,
        "contract_not_active",
    )
    ending = desk.active(start_date=days(-300), end_date=days(1))
    clock.set(NOW + timedelta(days=2))
    assert raise_on(ending["id"]).json()["detail"]["code"] == "contract_expired"
    clock.set(NOW)
    ended = desk.active()
    desk.ok(desk.post(f"/contracts/{ended['id']}/terminate", {"reason": "Ended", "effective_date": days(0)}))
    assert raise_on(ended["id"]).status_code == 409
    unknown = raise_on("00000000-0000-4000-8000-000000000000")
    assert (unknown.status_code, unknown.json()["detail"]["code"]) == (422, "unknown_contract")


def test_covered_item_must_belong_to_the_contract(desk):
    contract = desk.active()
    other_item = desk.item(desk.active()["id"])
    body = {"contract_id": contract["id"], "kind": "breakdown_call", "description": "x" * 5}
    refused = desk.post("/engagements", {**body, "covered_item_id": other_item["id"]}, desk.coordinator)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (422, "covered_item_not_in_contract")


def test_move_through_the_statuses_and_within_terms(desk, clock):
    contract = desk.active()  # response 4 hours, resolution 24 hours
    eng = desk.engagement(contract["id"])
    path = f"/engagements/{eng['id']}/status"
    assert desk.post(path, {"status": "resolved", "resolution_note": "Done"}, desk.coordinator).status_code == 409
    started = desk.ok(desk.post(path, {"status": "in_progress", "at": LATER}, desk.coordinator))
    assert (started["vendor_responded_at"], started["within_terms"]) == ("2026-11-01T12:00:00+00:00", None)
    missing = desk.post(path, {"status": "resolved"}, desk.coordinator)
    assert (missing.status_code, missing.json()["detail"]["code"]) == (422, "resolution_note_required")
    resolved = desk.ok(desk.post(path, {"status": "resolved", "resolution_note": "Rope replaced"}, desk.coordinator))
    assert (resolved["resolution_note"], resolved["within_terms"]) == ("Rope replaced", True)
    closed = desk.ok(desk.post(path, {"status": "closed"}, desk.coordinator))
    assert (closed["status"], closed["closed_at"]) == ("closed", "2026-11-01T09:00:00+00:00")
    assert desk.patch(f"/engagements/{eng['id']}", {"description": "Edited"}, desk.coordinator).status_code == 409
    # The clock is frozen, so entries share occurred_at; compare without relying on their order.
    actions = sorted(a for a, _ in audit(desk.org.id, eng["id"]))
    assert actions == ["engagement.closed", "engagement.in_progress", "engagement.raised", "engagement.resolved"]


def test_a_late_vendor_is_outside_terms_and_counted_on_the_contract(desk):
    contract = desk.active()
    eng = desk.engagement(contract["id"])
    path = f"/engagements/{eng['id']}/status"
    desk.ok(desk.post(path, {"status": "in_progress", "at": TOO_LATE}, desk.coordinator))
    assert desk.ok(desk.get(f"/engagements/{eng['id']}", desk.viewer))["within_terms"] is False
    counts = desk.ok(desk.get(f"/contracts/{contract['id']}"))["engagement_counts"]
    assert counts == {"open": 1, "resolved": 0, "outside_terms": 1}


def test_cancel_needs_a_note_kept_in_the_audit(desk):
    eng = desk.engagement(desk.active()["id"])
    path = f"/engagements/{eng['id']}/status"
    assert desk.post(path, {"status": "cancelled"}, desk.coordinator).json()["detail"]["code"] == "note_required"
    done = desk.ok(desk.post(path, {"status": "cancelled", "note": "Raised twice"}, desk.coordinator))
    assert done["status"] == "cancelled"
    assert ("engagement.cancelled", "Raised twice") in audit(desk.org.id, eng["id"])


def test_update_an_open_engagement(desk):
    contract = desk.active()
    item = desk.item(contract["id"])
    eng = desk.engagement(contract["id"], covered_item_id=item["id"])
    path = f"/engagements/{eng['id']}"
    edited = desk.ok(desk.patch(path, {"vendor_call_reference": "V-1", "covered_item_id": None}, desk.coordinator))
    assert (edited["vendor_call_reference"], edited["covered_item_id"]) == ("V-1", None)
    foreign = desk.item(desk.active()["id"])
    assert desk.patch(path, {"covered_item_id": foreign["id"]}, desk.coordinator).status_code == 422
    assert desk.get("/engagements/00000000-0000-4000-8000-000000000000").status_code == 404


def test_terminating_a_contract_leaves_its_open_engagements_open(desk):
    contract = desk.active()
    eng = desk.engagement(contract["id"])
    desk.ok(desk.post(f"/contracts/{contract['id']}/terminate", {"reason": "Ended", "effective_date": days(0)}))
    started = desk.post(f"/engagements/{eng['id']}/status", {"status": "in_progress"}, desk.coordinator)
    assert desk.ok(started)["status"] == "in_progress"


def test_list_filters_newest_first(desk):
    a = desk.active()
    b = desk.active()
    late = desk.engagement(a["id"], reported_at=(NOW - timedelta(hours=40)).isoformat())
    desk.ok(desk.post(f"/engagements/{late['id']}/status", {"status": "in_progress"}, desk.coordinator))
    visit = desk.engagement(b["id"], kind="preventive_visit", description="Service visit")

    def ids(query: str) -> list[str]:
        return [e["id"] for e in desk.ok(desk.get(f"/engagements{query}", desk.viewer))["items"]]

    assert ids(f"?contract_id={a['id']}") == [late["id"]]
    assert ids("?kind=preventive_visit")[:1] == [visit["id"]]
    assert visit["id"] in ids("?status=open") and late["id"] not in ids("?status=open")
    assert ids(f"?contract_id={a['id']}&within_terms=false") == [late["id"]]  # responded 40 hours later
    assert ids(f"?contract_id={b['id']}&within_terms=false") == []
    newest = ids(f"?contract_id={b['id']}")
    assert newest == [visit["id"]]
    assert desk.get("/engagements?status=lost", desk.viewer).status_code == 422
    assert desk.get("/engagements?kind=repair", desk.viewer).status_code == 422
