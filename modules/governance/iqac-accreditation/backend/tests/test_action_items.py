"""Action items and the counts behind the Governance widget (PRD flows 7 and 8)."""

from datetime import timedelta

from conftest import audit, days
from eos_core.db import new_id


def code(r) -> tuple[int, str]:
    return r.status_code, r.json()["detail"]["code"]


def test_record_an_action_item_open_and_linked_to_a_cycle_and_metric(desk):
    d = desk
    c = d.collecting()
    item = d.action_item(
        title="Fix the survey",
        description="From the peer team visit",
        source="Peer team visit",
        cycle_id=c["cycle"]["id"],
        metric_id=c["q"]["metric_id"],
    )
    assert item == {
        "id": item["id"],
        "organisation_id": d.org.id,
        "title": "Fix the survey",
        "description": "From the peer team visit",
        "source": "Peer team visit",
        "cycle_id": c["cycle"]["id"],
        "metric_id": c["q"]["metric_id"],
        "owner_id": d.alice_id,
        "due_on": days(10),
        "status": "open",
        "overdue": False,
        "completed_at": None,
    }
    assert audit(d.org.id, item["id"]) == [("action-item.created", None)]
    plain = d.action_item()
    assert (plain["description"], plain["source"], plain["cycle_id"], plain["metric_id"]) == (None, None, None, None)


def test_links_must_exist(desk):
    d = desk
    body = {"title": "x", "owner_id": d.alice_id, "due_on": days(5)}
    assert code(d.post("/action-items", {**body, "cycle_id": new_id()})) == (422, "cycle_not_found")
    assert code(d.post("/action-items", {**body, "metric_id": new_id()})) == (422, "metric_not_found")


def test_list_soonest_first_with_filters_and_pages(desk):
    d = desk
    c = d.cycle()
    far = d.action_item(title="far", due_on=days(30))
    near = d.action_item(title="near", due_on=days(2), owner_id=d.bob_id, cycle_id=c["id"])
    late = d.action_item(title="late", due_on=days(-4))
    listed = d.ok(d.get("/action-items"))["items"]
    assert [i["title"] for i in listed] == ["late", "near", "far"]
    assert [i["id"] for i in d.ok(d.get("/action-items?overdue=true"))["items"]] == [late["id"]]
    assert {i["id"] for i in d.ok(d.get("/action-items?overdue=false"))["items"]} == {near["id"], far["id"]}
    assert [i["id"] for i in d.ok(d.get(f"/action-items?owner={d.bob_id}"))["items"]] == [near["id"]]
    assert [i["id"] for i in d.ok(d.get(f"/action-items?cycle_id={c['id']}"))["items"]] == [near["id"]]
    assert [i["id"] for i in d.ok(d.get("/action-items?status=open&limit=1"))["items"]] == [late["id"]]
    page = d.ok(d.get("/action-items?limit=2"))
    rest = d.ok(d.get(f"/action-items?limit=2&cursor={page['next_cursor']}"))
    assert [i["title"] for i in page["items"] + rest["items"]] == ["late", "near", "far"] and rest[
        "next_cursor"
    ] is None
    assert d.ok(d.get("/action-items?status=done"))["items"] == []


def test_an_owner_sees_only_their_own_items_a_reader_sees_all(desk):
    d = desk
    mine = d.action_item(owner_id=d.alice_id)
    theirs = d.action_item(owner_id=d.bob_id)
    assert [i["id"] for i in d.ok(d.get("/action-items", d.alice))["items"]] == [mine["id"]]
    assert [i["id"] for i in d.ok(d.get("/action-items?owner=me", d.bob))["items"]] == [theirs["id"]]
    assert d.ok(d.get(f"/action-items?owner={d.bob_id}", d.alice))["items"] == []
    assert len(d.ok(d.get("/action-items", d.viewer))["items"]) == 2


def test_the_owner_moves_an_item_open_in_progress_done_and_nothing_else(desk, clock):
    d = desk
    item = d.action_item()
    path = f"/action-items/{item['id']}"
    assert code(d.patch(path, {"status": "done"}, d.alice)) == (409, "transition_not_allowed")  # not in order
    started = d.ok(d.patch(path, {"status": "in_progress", "note": "Started"}, d.alice))
    assert started["status"] == "in_progress" and started["completed_at"] is None
    clock.set(clock.now + timedelta(days=1))
    done = d.ok(d.patch(path, {"status": "done"}, d.alice))
    assert (done["status"], done["completed_at"]) == ("done", "2026-11-06T09:00:00+00:00")
    assert audit(d.org.id, item["id"]) == [
        ("action-item.created", None),
        ("action-item.status-changed", "open -> in_progress: Started"),
        ("action-item.status-changed", "in_progress -> done"),
    ]
    assert code(d.patch(path, {"status": "in_progress"}, d.alice)) == (409, "action_item_closed")


def test_an_owner_cannot_change_other_fields_cancel_or_touch_anothers_item(desk):
    d = desk
    item = d.action_item()
    path = f"/action-items/{item['id']}"
    assert code(d.patch(path, {"title": "mine now"}, d.alice)) == (403, "forbidden")
    assert code(d.patch(path, {"owner_id": d.alice_id, "status": "in_progress"}, d.alice)) == (403, "forbidden")
    assert code(d.patch(path, {"status": "cancelled"}, d.alice)) == (403, "forbidden")
    assert d.patch(path, {"status": "in_progress"}, d.bob).status_code == 404  # not bob's
    assert d.patch(path, {"status": "in_progress"}, d.viewer).status_code == 403  # read only
    assert d.patch(f"/action-items/{new_id()}", {"status": "in_progress"}, d.alice).status_code == 404
    assert d.ok(d.get("/action-items?status=open", d.coordinator))["items"][0]["title"] == item["title"]


def test_the_coordinator_changes_any_field_reassigns_and_cancels(desk):
    d = desk
    item = d.action_item()
    path = f"/action-items/{item['id']}"
    changed = d.ok(d.patch(path, {"title": "New title", "due_on": days(40), "source": "Audit", "owner_id": d.bob_id}))
    assert (changed["title"], changed["due_on"], changed["source"], changed["owner_id"]) == (
        "New title",
        days(40),
        "Audit",
        d.bob_id,
    )
    assert [a for a, _ in audit(d.org.id, item["id"])] == [
        "action-item.created",
        "action-item.updated",
        "action-item.reassigned",
    ]
    assert d.ok(d.patch(path, {})) == changed
    cancelled = d.ok(d.patch(path, {"status": "cancelled", "note": "Superseded"}))
    assert cancelled["status"] == "cancelled" and cancelled["completed_at"] is None
    assert audit(d.org.id, item["id"])[-1] == ("action-item.status-changed", "open -> cancelled: Superseded")
    assert code(d.patch(path, {"title": "Again"})) == (409, "action_item_closed")
    started = d.action_item()
    d.ok(d.patch(f"/action-items/{started['id']}", {"status": "in_progress"}))
    assert d.ok(d.patch(f"/action-items/{started['id']}", {"status": "cancelled"}))["status"] == "cancelled"


def test_a_coordinator_cannot_skip_the_order_either(desk):
    d = desk
    item = d.action_item()
    assert code(d.patch(f"/action-items/{item['id']}", {"status": "done"})) == (409, "transition_not_allowed")


def test_overdue_is_open_or_in_progress_and_past_due(desk):
    d = desk
    late = d.action_item(due_on=days(-1))
    today = d.action_item(due_on=days(0))
    assert late["overdue"] is True and today["overdue"] is False
    d.ok(d.patch(f"/action-items/{late['id']}", {"status": "in_progress"}))
    assert d.ok(d.get("/action-items?overdue=true"))["items"][0]["overdue"] is True
    d.ok(d.patch(f"/action-items/{late['id']}", {"status": "done"}))
    assert d.ok(d.get("/action-items?overdue=true"))["items"] == []  # a finished item is never overdue
    assert d.ok(d.get("/action-items?status=done"))["items"][0]["overdue"] is False


def test_stats_count_open_in_progress_overdue_and_due_soon(desk):
    d = desk
    empty = d.ok(d.get("/stats/action-items"))
    assert empty == {"open": 0, "in_progress": 0, "overdue": 0, "due_soon": 0, "due_soon_days": 14, "soonest": []}
    d.action_item(title="overdue", due_on=days(-2))
    d.action_item(title="today", due_on=days(0))
    edge = d.action_item(title="edge", due_on=days(14))
    d.action_item(title="beyond", due_on=days(15))
    started = d.action_item(title="started", due_on=days(3))
    d.ok(d.patch(f"/action-items/{started['id']}", {"status": "in_progress"}))
    finished = d.action_item(title="finished", due_on=days(1))
    d.ok(d.patch(f"/action-items/{finished['id']}", {"status": "in_progress"}))
    d.ok(d.patch(f"/action-items/{finished['id']}", {"status": "done"}))
    gone = d.action_item(title="cancelled", due_on=days(1))
    d.ok(d.patch(f"/action-items/{gone['id']}", {"status": "cancelled"}))
    stats = d.ok(d.get("/stats/action-items", d.viewer))
    assert (stats["open"], stats["in_progress"], stats["overdue"], stats["due_soon"], stats["due_soon_days"]) == (
        4,
        1,
        1,
        3,  # today, started, edge (day 14); not beyond (day 15) nor the overdue one
        14,
    )
    assert [i["title"] for i in stats["soonest"]] == ["overdue", "today", "started", "edge", "beyond"]
    assert stats["soonest"][0] == {
        "id": stats["soonest"][0]["id"],
        "title": "overdue",
        "owner_id": d.alice_id,
        "due_on": days(-2),
        "status": "open",
        "overdue": True,
    }
    assert edge["id"] in {i["id"] for i in stats["soonest"]}


def test_stats_list_at_most_ten_and_follow_the_configured_window(desk, monkeypatch):
    d = desk
    for n in range(12):
        d.action_item(title=f"item {n:02d}", due_on=days(n))
    stats = d.ok(d.get("/stats/action-items"))
    assert [i["title"] for i in stats["soonest"]] == [f"item {n:02d}" for n in range(10)]
    assert stats["open"] == 12
    monkeypatch.setenv("IQAC_ACCREDITATION_DUE_SOON_DAYS", "3")
    short = d.ok(d.get("/stats/action-items"))
    assert (short["due_soon"], short["due_soon_days"]) == (4, 3)


def test_stats_cover_every_item_of_the_organisation_not_just_the_callers(desk):
    d = desk
    d.action_item(owner_id=d.bob_id)
    assert d.ok(d.get("/stats/action-items"))["open"] == 1
