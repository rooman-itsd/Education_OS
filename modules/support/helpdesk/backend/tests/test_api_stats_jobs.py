"""The Support Staff widget endpoint (GET /stats/open-by-priority) and the daily auto-close job, end to end."""

from datetime import timedelta

from conftest import NOW, outbox


def rows(body):
    return {r["priority"]: r for r in body["rows"]}


def test_open_by_priority_for_an_agent_in_the_queue(desk):
    first = desk.raise_ticket()
    desk.raise_ticket("Second")
    desk.ok(desk.post(f"/tickets/{first['id']}/assign", {}, desk.agent))
    body = desk.ok(desk.get("/stats/open-by-priority", desk.agent))
    assert (body["scope"], body["total_open"]) == ("my_queues", 2)
    high = rows(body)["high"]
    assert (high["open"], high["unassigned"], high["assigned_to_me"], high["on_hold"]) == (2, 1, 1, 0)
    assert [r["priority"] for r in body["rows"]] == ["urgent", "high", "medium", "low"]
    assert rows(body)["low"]["oldest_created_at"] is None


def test_scope_mine_all_and_forbidden(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/assign", {}, desk.agent))
    assert desk.ok(desk.get("/stats/open-by-priority?scope=mine", desk.agent2))["total_open"] == 0
    assert desk.ok(desk.get("/stats/open-by-priority?scope=mine", desk.agent))["total_open"] == 1
    assert desk.ok(desk.get("/stats/open-by-priority?scope=all", desk.lead))["total_open"] == 1
    r = desk.get("/stats/open-by-priority?scope=all", desk.agent)
    assert (r.status_code, r.json()["detail"]["code"]) == (403, "forbidden")
    assert desk.get("/stats/open-by-priority", desk.requester).status_code == 403
    assert desk.get("/stats/open-by-priority?scope=everything", desk.agent).status_code == 422


def test_queue_id_narrows_and_a_hidden_queue_counts_nothing(desk):
    desk.raise_ticket()
    assert desk.ok(desk.get(f"/stats/open-by-priority?queue_id={desk.it['id']}", desk.agent))["total_open"] == 1
    assert desk.ok(desk.get(f"/stats/open-by-priority?queue_id={desk.office['id']}", desk.agent))["total_open"] == 0
    assert (
        desk.ok(desk.get(f"/stats/open-by-priority?scope=all&queue_id={desk.it['id']}", desk.lead))["total_open"] == 1
    )


def test_closed_tickets_are_not_counted(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Done"}, desk.agent))
    assert desk.ok(desk.get("/stats/open-by-priority", desk.agent))["total_open"] == 0


# --- the daily auto-close job


def _resolve(desk, title):
    t = desk.raise_ticket(title)
    desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Fixed"}, desk.agent))
    return t


def test_auto_close_closes_only_tickets_resolved_more_than_the_days_ago(desk, clock):
    from eos_core.db import SessionLocal
    from eos_helpdesk.application.jobs import run_auto_close

    old = _resolve(desk, "Old")
    clock.set(NOW + timedelta(days=3))
    recent = _resolve(desk, "Recent")
    with SessionLocal() as db:
        closed = run_auto_close(db, now=NOW + timedelta(days=7, seconds=1))
    assert closed >= 1
    assert desk.ok(desk.get(f"/tickets/{old['id']}", desk.lead))["status"] == "closed"
    assert desk.ok(desk.get(f"/tickets/{recent['id']}", desk.lead))["status"] == "resolved"
    event = next(e for e in outbox("helpdesk.ticket.closed", desk.org.id) if e["ticket_id"] == old["id"])
    assert (event["closed_by"], event["satisfaction_rating"]) == (None, None)
    with SessionLocal() as db:  # idempotent: a second run closes nothing more of this organisation's
        run_auto_close(db, now=NOW + timedelta(days=7, seconds=1))
    assert len([e for e in outbox("helpdesk.ticket.closed", desk.org.id) if e["ticket_id"] == old["id"]]) == 1
