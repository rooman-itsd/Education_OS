"""Working tickets through the HTTP API: raising on someone's behalf, the queue list, assignment, replies and notes,
status, reclassifying, resolving, cancelling and links."""

from conftest import audit, outbox


def ev(desk, name):
    return outbox(f"helpdesk.ticket.{name}", desk.org.id)


# --- raising on someone's behalf (POST /tickets)


def test_an_agent_raises_a_ticket_for_a_walk_in(desk):
    body = {
        "category_id": desk.category["id"],
        "title": "Laptop will not boot",
        "description": "Came to the desk",
        "requester_id": desk.requester_id,
        "channel": "walk_in",
        "priority": "urgent",
    }
    t = desk.ok(desk.post("/tickets", body, desk.agent))
    assert (t["requester_id"], t["raised_by_id"], t["channel"], t["priority"]) == (
        desk.requester_id,
        desk.agent_id,
        "walk_in",
        "urgent",
    )
    assert t["assignee_id"] is None
    assert ev(desk, "assigned") == []
    mine = desk.ok(desk.get("/me/tickets", desk.requester))["items"]
    assert [m["id"] for m in mine] == [t["id"]]


def test_assign_to_me_assigns_and_publishes_assigned_after_created(desk):
    body = {
        "category_id": desk.category["id"],
        "title": "Phone call",
        "description": "Called the desk",
        "requester_id": desk.requester_id,
        "channel": "phone",
        "assign_to_me": True,
    }
    t = desk.ok(desk.post("/tickets", body, desk.agent))
    assert t["assignee_id"] == desk.agent_id
    [assigned] = ev(desk, "assigned")
    assert (assigned["assignee_id"], assigned["previous_assignee_id"]) == (desk.agent_id, None)


def test_ticket_numbers_follow_the_organisation_sequence(desk):
    numbers = [desk.raise_ticket(f"Issue {i}")["number"] for i in range(3)]
    assert numbers == ["HD-000001", "HD-000002", "HD-000003"]


def test_raising_needs_an_active_category_and_few_enough_attachments(desk):
    body = {"name": "Account access", "default_queue_id": desk.it["id"], "default_priority": "high", "active": False}
    desk.ok(desk.patch(f"/categories/{desk.category['id']}", body, desk.admin))
    r = desk.post(
        "/me/tickets", {"category_id": desk.category["id"], "title": "Hello", "description": "Hi!"}, desk.requester
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "category_inactive")
    body["active"] = True
    desk.ok(desk.patch(f"/categories/{desk.category['id']}", body, desk.admin))
    many = {
        "category_id": desk.category["id"],
        "title": "Photos",
        "description": "Six photos",
        "attachment_document_ids": [f"doc-{i}" for i in range(6)],
    }
    r = desk.post("/me/tickets", many, desk.requester)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "too_many_attachments")


def test_requesters_cannot_raise_for_others(desk):
    body = {
        "category_id": desk.category["id"],
        "title": "Hello",
        "description": "Hi there",
        "requester_id": desk.agent_id,
        "channel": "email",
    }
    assert desk.post("/tickets", body, desk.requester).status_code == 403


# --- the queue list and one ticket


def test_agents_see_their_queues_and_leads_see_every_queue(desk):
    t = desk.raise_ticket()
    assert [i["id"] for i in desk.ok(desk.get("/tickets", desk.agent))["items"]] == [t["id"]]
    assert desk.ok(desk.get("/tickets", desk.outsider))["items"] == []
    assert desk.get(f"/tickets/{t['id']}", desk.outsider).status_code == 404
    assert [i["id"] for i in desk.ok(desk.get("/tickets", desk.viewer))["items"]] == [t["id"]]


def test_ticket_list_filters_sort_and_pages(desk):
    first = desk.raise_ticket("Wifi down")
    second = desk.raise_ticket("Printer jam")
    desk.ok(desk.post(f"/tickets/{first['id']}/assign", {}, desk.agent))
    page = desk.ok(desk.get("/tickets?limit=1", desk.lead))
    assert len(page["items"]) == 1 and page["next_cursor"]
    rest = desk.ok(desk.get(f"/tickets?limit=1&cursor={page['next_cursor']}", desk.lead))
    assert {page["items"][0]["id"], rest["items"][0]["id"]} == {first["id"], second["id"]}
    assert rest["next_cursor"] is None
    assert [i["id"] for i in desk.ok(desk.get("/tickets?assignee=unassigned", desk.lead))["items"]] == [second["id"]]
    assert [i["id"] for i in desk.ok(desk.get("/tickets?assignee=me", desk.agent))["items"]] == [first["id"]]
    assert [i["id"] for i in desk.ok(desk.get("/tickets?q=wifi", desk.lead))["items"]] == [first["id"]]
    assert [i["id"] for i in desk.ok(desk.get("/tickets?q=HD-000002", desk.lead))["items"]] == [second["id"]]
    assert desk.ok(desk.get("/tickets?status=resolved,closed", desk.lead))["items"] == []
    assert desk.get("/tickets?status=open", desk.lead).status_code == 422


def test_a_ticket_shows_replies_internal_notes_and_links(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/comments", {"visibility": "internal", "body": "Known issue"}, desk.agent))
    desk.ok(
        desk.post(
            f"/tickets/{t['id']}/links", {"module": "maintenance", "entity": "ticket", "ref_id": "w1"}, desk.agent
        )
    )
    detail = desk.ok(desk.get(f"/tickets/{t['id']}", desk.agent))
    assert [c["visibility"] for c in detail["comments"]] == ["internal"]
    assert [link["module"] for link in detail["links"]] == ["maintenance"]


# --- assignment (POST /tickets/{id}/assign)


def test_an_agent_picks_up_by_naming_themselves(desk):
    t = desk.raise_ticket()
    assert (
        desk.ok(desk.post(f"/tickets/{t['id']}/assign", {"assignee_id": desk.agent_id}, desk.agent))["assignee_id"]
        == desk.agent_id
    )


def test_an_agent_needs_manage_for_anything_but_picking_up(desk):
    t = desk.raise_ticket()
    assert desk.post(f"/tickets/{t['id']}/assign", {"assignee_id": desk.agent2_id}, desk.agent).status_code == 403
    assert desk.post(f"/tickets/{t['id']}/assign", {"queue_id": desk.office["id"]}, desk.agent).status_code == 403
    desk.ok(desk.post(f"/tickets/{t['id']}/assign", {}, desk.agent2))
    assert desk.post(f"/tickets/{t['id']}/assign", {}, desk.agent).status_code == 403  # already assigned


def test_a_lead_assigns_unassigns_and_moves(desk):
    t = desk.raise_ticket()
    tid = t["id"]
    assert (
        desk.ok(desk.post(f"/tickets/{tid}/assign", {"assignee_id": desk.agent2_id}, desk.lead))["assignee_id"]
        == desk.agent2_id
    )
    assert desk.ok(desk.post(f"/tickets/{tid}/assign", {"assignee_id": None}, desk.lead))["assignee_id"] is None
    desk.ok(desk.post(f"/tickets/{tid}/assign", {"assignee_id": desk.agent_id}, desk.lead))
    moved = desk.ok(desk.post(f"/tickets/{tid}/assign", {"queue_id": desk.office["id"]}, desk.lead))
    assert (moved["queue_id"], moved["assignee_id"], moved["status"]) == (desk.office["id"], None, "new")
    last = ev(desk, "assigned")[-1]
    assert (last["previous_queue_id"], last["queue_id"], last["previous_assignee_id"]) == (
        desk.it["id"],
        desk.office["id"],
        desk.agent_id,
    )


def test_the_assignee_must_be_in_the_target_queue(desk):
    t = desk.raise_ticket()
    r = desk.post(
        f"/tickets/{t['id']}/assign", {"queue_id": desk.office["id"], "assignee_id": desk.agent_id}, desk.lead
    )
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "assignee_not_in_queue")


def test_closed_or_cancelled_tickets_cannot_be_assigned(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/cancel", {"reason": "Raised twice"}, desk.lead))
    assert desk.post(f"/tickets/{t['id']}/assign", {"assignee_id": desk.agent_id}, desk.lead).status_code == 409


# --- replies, notes and status


def test_an_internal_note_is_not_a_response(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/comments", {"visibility": "internal", "body": "Checking"}, desk.agent))
    again = desk.ok(desk.get(f"/tickets/{t['id']}", desk.agent))
    assert (again["status"], again["first_responded_at"]) == ("new", None)
    assert ev(desk, "responded") == []


def test_a_hold_note_is_a_public_reply_and_the_first_response(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/status", {"status": "in_progress"}, desk.agent))
    body = {"status": "on_hold", "hold_reason": "waiting_third_party", "note": "Waiting on the vendor"}
    desk.ok(desk.post(f"/tickets/{t['id']}/status", body, desk.agent))
    [responded] = ev(desk, "responded")
    assert responded["responded_by"] == desk.agent_id
    assert [c["body"] for c in desk.ok(desk.get(f"/me/tickets/{t['id']}", desk.requester))["comments"]] == [
        "Waiting on the vendor"
    ]


def test_status_rules_answer_409_and_422(desk):
    t = desk.raise_ticket()
    r = desk.post(f"/tickets/{t['id']}/status", {"status": "on_hold", "hold_reason": "waiting_internal"}, desk.agent)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "transition_not_allowed")
    desk.ok(desk.post(f"/tickets/{t['id']}/status", {"status": "in_progress"}, desk.agent))
    r = desk.post(f"/tickets/{t['id']}/status", {"status": "on_hold"}, desk.agent)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "hold_reason_required")


def test_a_requester_reply_moves_only_a_ticket_waiting_on_them(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/status", {"status": "in_progress"}, desk.agent))
    desk.ok(
        desk.post(f"/tickets/{t['id']}/status", {"status": "on_hold", "hold_reason": "waiting_third_party"}, desk.agent)
    )
    desk.ok(desk.post(f"/me/tickets/{t['id']}/comments", {"body": "Any news?"}, desk.requester))
    assert desk.ok(desk.get(f"/tickets/{t['id']}", desk.agent))["status"] == "on_hold"


def test_viewers_and_requesters_cannot_work_tickets(desk):
    t = desk.raise_ticket()
    for headers in (desk.viewer, desk.requester):
        assert (
            desk.post(f"/tickets/{t['id']}/comments", {"visibility": "public", "body": "x"}, headers).status_code == 403
        )
        assert desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Done"}, headers).status_code == 403
        assert desk.post(f"/tickets/{t['id']}/cancel", {"reason": "Nope"}, headers).status_code == 403


# --- reclassify (PATCH /tickets/{id})


def test_the_assignee_changes_priority_with_a_reason(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/assign", {}, desk.agent))
    r = desk.patch(f"/tickets/{t['id']}", {"priority": "urgent"}, desk.agent)
    assert (r.status_code, r.json()["detail"]["code"]) == (422, "reason_required")
    changed = desk.ok(desk.patch(f"/tickets/{t['id']}", {"priority": "urgent", "reason": "Exams today"}, desk.agent))
    assert changed["priority"] == "urgent"
    [reclassified] = ev(desk, "reclassified")
    assert (reclassified["previous_priority"], reclassified["priority"]) == ("high", "urgent")
    assert ("ticket.reclassified", "Exams today") in audit(desk.org.id, t["id"])


def test_an_agent_not_assigned_or_changing_the_category_needs_manage(desk):
    t = desk.raise_ticket()
    assert desk.patch(f"/tickets/{t['id']}", {"priority": "low", "reason": "x"}, desk.agent).status_code == 403
    other = desk.ok(
        desk.post(
            "/categories",
            {"name": "Fees", "default_queue_id": desk.office["id"], "default_priority": "low"},
            desk.admin,
        )
    )
    desk.ok(desk.post(f"/tickets/{t['id']}/assign", {}, desk.agent))
    assert desk.patch(f"/tickets/{t['id']}", {"category_id": other["id"], "reason": "x"}, desk.agent).status_code == 403
    moved = desk.ok(
        desk.patch(f"/tickets/{t['id']}", {"category_id": other["id"], "reason": "Fees question"}, desk.lead)
    )
    assert (moved["category_id"], moved["queue_id"]) == (other["id"], desk.it["id"])


def test_a_title_change_publishes_nothing(desk):
    t = desk.raise_ticket()
    desk.ok(desk.patch(f"/tickets/{t['id']}", {"title": "Cannot sign in to email"}, desk.lead))
    assert ev(desk, "reclassified") == []


def test_resolved_tickets_cannot_be_changed(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Fixed"}, desk.agent))
    assert desk.patch(f"/tickets/{t['id']}", {"title": "New title"}, desk.lead).status_code == 409


# --- resolve and cancel


def test_a_new_ticket_can_be_resolved_straight_away(desk):
    t = desk.raise_ticket()
    resolved = desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Answered"}, desk.agent))
    assert (resolved["status"], resolved["resolution_note"]) == ("resolved", "Answered")
    assert desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Again"}, desk.agent).status_code == 409


def test_cancel_as_a_duplicate(desk):
    original = desk.raise_ticket("Wifi down")
    copy = desk.raise_ticket("Wifi down again")
    r = desk.post(f"/tickets/{copy['id']}/cancel", {"reason": "Same", "duplicate_of": copy["id"]}, desk.lead)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "duplicate_of_itself")
    unknown = "00000000-0000-4000-8000-000000000000"
    r = desk.post(f"/tickets/{copy['id']}/cancel", {"reason": "Same", "duplicate_of": unknown}, desk.lead)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "invalid_duplicate")
    cancelled = desk.ok(
        desk.post(f"/tickets/{copy['id']}/cancel", {"reason": "Same", "duplicate_of": original["id"]}, desk.lead)
    )
    assert (cancelled["status"], cancelled["duplicate_of"]) == ("cancelled", original["id"])
    assert ev(desk, "cancelled")[0]["duplicate_of"] == original["id"]
    assert desk.post(f"/tickets/{copy['id']}/cancel", {"reason": "Again"}, desk.lead).status_code == 409


def test_an_agent_cannot_cancel(desk):
    t = desk.raise_ticket()
    assert desk.post(f"/tickets/{t['id']}/cancel", {"reason": "Not mine"}, desk.agent).status_code == 403


def test_closed_tickets_take_no_replies(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/cancel", {"reason": "Raised by mistake"}, desk.lead))
    r = desk.post(f"/tickets/{t['id']}/comments", {"visibility": "public", "body": "Hello"}, desk.agent)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "ticket_final")


# --- links


def test_links_are_added_once_and_removed_with_an_audit_entry(desk):
    t = desk.raise_ticket()
    body = {"module": "knowledge-base", "entity": "article", "ref_id": "kb-12", "note": "See article"}
    link = desk.ok(desk.post(f"/tickets/{t['id']}/links", body, desk.agent))
    assert (link["created_by"], link["ticket_id"]) == (desk.agent_id, t["id"])
    assert desk.post(f"/tickets/{t['id']}/links", body, desk.agent).status_code == 409
    assert (
        desk.client.delete(f"/api/v1/helpdesk/tickets/{t['id']}/links/{link['id']}", headers=desk.agent).status_code
        == 204
    )
    assert (
        desk.client.delete(f"/api/v1/helpdesk/tickets/{t['id']}/links/{link['id']}", headers=desk.agent).status_code
        == 404
    )
    assert ("link.removed", None) in audit(desk.org.id, t["id"])
