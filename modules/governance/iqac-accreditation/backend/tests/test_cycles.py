"""Cycles: open, change while planning, move through the statuses, assign metrics (PRD flows 2, 3 and 6)."""

from datetime import timedelta

from conftest import audit, days, outbox
from eos_core.db import new_id


def test_open_a_cycle_in_planning_and_list_newest_first(desk, clock):
    d = desk
    f = d.framework()
    first = d.cycle(f["id"], name="2024-25")
    clock.set(clock.now + timedelta(minutes=1))
    second = d.cycle(f["id"], name="2025-26")
    assert first["status"] == "planning" and first["submitted_on"] is None and first["closed_at"] is None
    assert first["period_start"] == "2025-04-01" and first["organisation_id"] == d.org.id
    assert [c["name"] for c in d.ok(d.get("/cycles"))] == ["2025-26", "2024-25"]
    d.move(second["id"], "collecting")
    assert [c["id"] for c in d.ok(d.get("/cycles?status=collecting"))] == [second["id"]]
    assert {c["id"] for c in d.ok(d.get(f"/cycles?framework_id={f['id']}"))} == {first["id"], second["id"]}
    assert d.ok(d.get(f"/cycles?framework_id={new_id()}")) == []
    assert audit(d.org.id, first["id"]) == [("cycle.created", None)]


def test_cycle_period_must_end_after_it_starts_and_the_framework_must_be_active(desk):
    d = desk
    f = d.framework()
    for start, end in (("2026-03-31", "2025-04-01"), ("2025-04-01", "2025-04-01")):
        r = d.post("/cycles", {"framework_id": f["id"], "name": "x", "period_start": start, "period_end": end})
        assert (r.status_code, r.json()["detail"]["code"]) == (422, "period_end_not_after_start"), (start, end)
    off = d.framework(active=False)
    r = d.post(
        "/cycles", {"framework_id": off["id"], "name": "x", "period_start": "2025-04-01", "period_end": "2026-03-31"}
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "framework_inactive")
    r = d.post(
        "/cycles", {"framework_id": new_id(), "name": "x", "period_start": "2025-04-01", "period_end": "2026-03-31"}
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "framework_not_found")


def test_cycle_detail_counts_responses_by_status_and_overdue(desk):
    d = desk
    c = d.collecting()
    counts = d.ok(d.get(f"/cycles/{c['cycle']['id']}"))["response_counts"]
    assert counts == {"pending": 2, "submitted": 0, "returned": 0, "accepted": 0, "overdue": 0}
    d.ok(d.put(f"/responses/{c['q']['id']}", {"value": 1}, d.alice))
    d.ok(d.post(f"/responses/{c['q']['id']}/submit", None, d.alice))
    # Eleven days on, bob's response (due in 20 days) is not late, a new one due yesterday is.
    late = d.assign(c["cycle"]["id"], (d.metric(c["framework"]["id"])["id"], d.bob_id, days(-1)))[0]
    counts = d.ok(d.get(f"/cycles/{c['cycle']['id']}"))["response_counts"]
    assert counts == {"pending": 2, "submitted": 1, "returned": 0, "accepted": 0, "overdue": 1}
    assert d.ok(d.get(f"/responses/{late['id']}"))["overdue"] is True
    assert d.get(f"/cycles/{new_id()}").status_code == 404


def test_a_cycle_is_renamed_or_given_another_period_only_while_planning(desk):
    d = desk
    c = d.cycle()
    r = d.ok(d.patch(f"/cycles/{c['id']}", {"name": "Renamed", "period_end": "2026-06-30"}))
    assert (r["name"], r["period_start"], r["period_end"]) == ("Renamed", "2025-04-01", "2026-06-30")
    bad = d.patch(f"/cycles/{c['id']}", {"period_start": "2026-07-01"})  # now after the stored end
    assert (bad.status_code, bad.json()["detail"]["code"]) == (422, "period_end_not_after_start")
    assert d.ok(d.patch(f"/cycles/{c['id']}", {})) == r
    d.move(c["id"], "collecting")
    again = d.patch(f"/cycles/{c['id']}", {"name": "Late"})
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "cycle_not_planning")
    assert d.patch(f"/cycles/{new_id()}", {"name": "x"}).status_code == 404


def test_status_moves_in_order_and_publishes_each_change(desk):
    d = desk
    c = d.cycle()
    d.move(c["id"], "collecting")
    d.move(c["id"], "under_review")
    done = d.move(c["id"], "submitted", submitted_on="2026-06-01")
    assert (done["status"], done["submitted_on"], done["closed_at"]) == ("submitted", "2026-06-01", None)
    closed = d.move(c["id"], "closed")
    assert closed["status"] == "closed" and closed["closed_at"].startswith("2026-11-05T09:00")
    published = outbox("iqac-accreditation.cycle.status-changed", d.org.id)
    assert [(p["from_status"], p["to_status"]) for p in published] == [
        ("planning", "collecting"),
        ("collecting", "under_review"),
        ("under_review", "submitted"),
        ("submitted", "closed"),
    ]
    assert published[0] == {
        "organisation_id": d.org.id,
        "cycle_id": c["id"],
        "framework_id": c["framework_id"],
        "from_status": "planning",
        "to_status": "collecting",
        "changed_at": "2026-11-05T09:00:00+00:00",
    }
    assert audit(d.org.id, c["id"])[1] == ("cycle.status-changed", "planning -> collecting")


def test_status_moves_that_skip_or_go_back_are_refused_without_an_event(desk):
    d = desk
    c = d.cycle()
    for target in ("under_review", "submitted", "closed"):
        r = d.post(f"/cycles/{c['id']}/status", {"status": target, "submitted_on": "2026-06-01"})
        assert (r.status_code, r.json()["detail"]["code"]) == (409, "transition_not_allowed"), target
    d.move(c["id"], "collecting")
    r = d.post(f"/cycles/{c['id']}/status", {"status": "collecting"})
    assert r.status_code == 409
    assert d.post(f"/cycles/{c['id']}/status", {"status": "planning"}).status_code == 422  # not a target
    assert len(outbox("iqac-accreditation.cycle.status-changed", d.org.id)) == 1
    assert d.post(f"/cycles/{new_id()}/status", {"status": "collecting"}).status_code == 404


def test_submitting_needs_the_date_and_every_response_accepted(desk):
    d = desk
    c = d.submitted_q()
    cid = c["cycle"]["id"]
    d.move(cid, "under_review")
    missing = d.post(f"/cycles/{cid}/status", {"status": "submitted"})
    assert (missing.status_code, missing.json()["detail"]["code"]) == (422, "submitted_on_required")
    blocked = d.post(f"/cycles/{cid}/status", {"status": "submitted", "submitted_on": "2026-06-01"})
    assert (blocked.status_code, blocked.json()["detail"]["code"]) == (409, "responses_not_accepted")
    # The submitted one is accepted, the pending one of bob still blocks.
    d.ok(d.post(f"/responses/{c['q']['id']}/review", {"decision": "accept"}))
    assert d.post(f"/cycles/{cid}/status", {"status": "submitted", "submitted_on": "2026-06-01"}).status_code == 409
    d.ok(d.put(f"/responses/{c['n']['id']}", {"narrative": "We did it."}, d.bob))
    d.ok(d.post(f"/responses/{c['n']['id']}/submit", None, d.bob))
    d.ok(d.post(f"/responses/{c['n']['id']}/review", {"decision": "accept"}))
    assert d.move(cid, "submitted", submitted_on="2026-06-01")["status"] == "submitted"


def test_a_cycle_without_responses_can_be_submitted(desk):
    d = desk
    c = d.cycle()
    d.move(c["id"], "collecting")
    d.move(c["id"], "under_review")
    assert d.move(c["id"], "submitted", submitted_on="2026-06-01")["submitted_on"] == "2026-06-01"


def test_assignments_create_one_pending_response_per_metric(desk):
    d = desk
    c = d.collecting()
    r = c["q"]
    assert (r["status"], r["owner_id"], r["due_on"], r["metric_code"], r["overdue"]) == (
        "pending",
        d.alice_id,
        days(10),
        "Q1",
        False,
    )
    assert r["value"] is None and r["narrative"] is None and r["review_comment"] is None
    assert audit(d.org.id, r["id"]) == [("response.assigned", None)]
    # More metrics can be assigned while collecting.
    extra = d.metric(c["framework"]["id"])
    assert d.assign(c["cycle"]["id"], (extra["id"], d.bob_id, days(30)))[0]["metric_id"] == extra["id"]


def test_assignment_conflicts_and_unknown_metrics(desk):
    d = desk
    c = d.collecting()
    cid, q = c["cycle"]["id"], c["metrics"][0]
    again = d.post(
        f"/cycles/{cid}/assignments", {"assignments": [{"metric_id": q["id"], "owner_id": d.bob_id, "due_on": days(5)}]}
    )
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "metric_already_assigned")
    fresh = d.metric(c["framework"]["id"])
    twice = {"metric_id": fresh["id"], "owner_id": d.bob_id, "due_on": days(5)}
    assert d.post(f"/cycles/{cid}/assignments", {"assignments": [twice, twice]}).status_code == 409
    elsewhere = d.metric(d.framework()["id"])
    for metric_id, code in ((elsewhere["id"], "metric_not_in_framework"), (new_id(), "metric_not_found")):
        item = {"metric_id": metric_id, "owner_id": d.bob_id, "due_on": days(5)}
        r = d.post(f"/cycles/{cid}/assignments", {"assignments": [twice, item]})
        assert (r.status_code, r.json()["detail"]["code"]) == (422, code)
    # Nothing was created by the refused requests, not even the valid first item.
    assert len(d.ok(d.get(f"/responses?cycle_id={cid}"))["items"]) == 2
    assert d.post(f"/cycles/{new_id()}/assignments", {"assignments": [twice]}).status_code == 404


def test_assignments_are_closed_once_the_cycle_is_under_review(desk):
    d = desk
    c = d.collecting()
    d.move(c["cycle"]["id"], "under_review")
    fresh = d.metric(c["framework"]["id"])
    r = d.post(
        f"/cycles/{c['cycle']['id']}/assignments",
        {"assignments": [{"metric_id": fresh["id"], "owner_id": d.bob_id, "due_on": days(5)}]},
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "cycle_not_assignable")
    planning = d.cycle(c["framework"]["id"])  # planning is fine
    assert d.assign(planning["id"], (fresh["id"], d.bob_id, days(5)))
