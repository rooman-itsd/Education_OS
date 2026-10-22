"""A ticket's whole life through the HTTP API, with the events each step publishes (contracts/events.yaml)."""

from datetime import timedelta

from conftest import NOW, audit, outbox

EVENT_FIELDS = {
    "created": {
        "organisation_id",
        "ticket_id",
        "number",
        "requester_id",
        "raised_by_id",
        "channel",
        "category_id",
        "queue_id",
        "priority",
        "created_at",
    },
    "assigned": {
        "organisation_id",
        "ticket_id",
        "number",
        "queue_id",
        "previous_queue_id",
        "assignee_id",
        "previous_assignee_id",
        "assigned_by",
    },
    "responded": {"organisation_id", "ticket_id", "number", "responded_by", "responded_at"},
    "status-changed": {
        "organisation_id",
        "ticket_id",
        "number",
        "from_status",
        "to_status",
        "hold_reason",
        "changed_at",
    },
    "resolved": {"organisation_id", "ticket_id", "number", "requester_id", "resolved_by", "resolved_at"},
    "closed": {"organisation_id", "ticket_id", "number", "closed_by", "satisfaction_rating", "closed_at"},
}


def events(desk, name):
    return outbox(f"helpdesk.ticket.{name}", desk.org.id)


def test_raise_pick_up_reply_hold_answer_resolve_confirm(desk, clock):
    ticket = desk.raise_ticket()
    assert ticket["status"] == "new"
    assert (ticket["channel"], ticket["queue_id"], ticket["priority"]) == ("portal", desk.it["id"], "high")
    assert ticket["requester_id"] == ticket["raised_by_id"] == desk.requester_id
    assert ticket["number"] == "HD-000001"
    tid = ticket["id"]

    picked = desk.ok(desk.post(f"/tickets/{tid}/assign", {}, desk.agent))
    assert (picked["assignee_id"], picked["status"]) == (desk.agent_id, "new")

    reply = desk.ok(desk.post(f"/tickets/{tid}/comments", {"visibility": "public", "body": "Try now"}, desk.agent))
    assert reply["author_is_requester"] is False
    t = desk.ok(desk.get(f"/tickets/{tid}", desk.agent))
    assert t["status"] == "in_progress"

    held = desk.ok(
        desk.post(f"/tickets/{tid}/status", {"status": "on_hold", "hold_reason": "waiting_requester"}, desk.agent)
    )
    assert (held["status"], held["hold_reason"]) == ("on_hold", "waiting_requester")

    desk.ok(desk.post(f"/me/tickets/{tid}/comments", {"body": "Still stuck"}, desk.requester))
    assert desk.ok(desk.get(f"/me/tickets/{tid}", desk.requester))["status"] == "in_progress"

    resolved = desk.ok(desk.post(f"/tickets/{tid}/resolve", {"resolution_note": "Reset the account"}, desk.agent))
    assert resolved["status"] == "resolved"
    mine = desk.ok(desk.get(f"/me/tickets/{tid}", desk.requester))
    assert mine["can_reopen"] is True

    clock.set(NOW + timedelta(hours=2))
    closed = desk.ok(
        desk.post(f"/me/tickets/{tid}/confirm", {"satisfaction_rating": 5, "feedback": "Thanks"}, desk.requester)
    )
    assert (closed["status"], closed["satisfaction_rating"], closed["feedback"]) == ("closed", 5, "Thanks")

    for name, fields in EVENT_FIELDS.items():
        published = events(desk, name)
        assert published, name
        assert all(set(p) == fields for p in published), name
    assert len(events(desk, "responded")) == 1
    moves = [(e["from_status"], e["to_status"]) for e in events(desk, "status-changed")]
    assert moves == [("new", "in_progress"), ("in_progress", "on_hold"), ("on_hold", "in_progress")]
    assert events(desk, "closed")[0]["closed_by"] == desk.requester_id
    actions = sorted(a for a, _ in audit(desk.org.id, tid))  # the clock is frozen, so order by name
    assert actions == sorted(
        [
            "ticket.created",
            "ticket.assigned",
            "comment.public",
            "ticket.on_hold",
            "comment.public",
            "ticket.resolved",
            "ticket.closed",
        ]
    )
    assert all("Password" not in str(p) for name in EVENT_FIELDS for p in events(desk, name))
