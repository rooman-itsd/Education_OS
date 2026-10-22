"""The requester's own tickets through the HTTP API (/me/tickets): only their own, public replies only, confirm,
reopen within the window and withdraw."""

from datetime import timedelta

from conftest import NOW, audit, outbox


def test_a_requester_sees_only_their_own_tickets(desk):
    mine = desk.raise_ticket()
    other_id, other = desk.org.user("helpdesk-requester")
    theirs = desk.raise_ticket("Theirs", headers=other)
    assert [t["id"] for t in desk.ok(desk.get("/me/tickets", desk.requester))["items"]] == [mine["id"]]
    assert desk.get(f"/me/tickets/{theirs['id']}", desk.requester).status_code == 404
    assert theirs["requester_id"] == other_id


def test_internal_notes_and_links_are_never_shown_to_the_requester(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/comments", {"visibility": "internal", "body": "Secret"}, desk.agent))
    desk.ok(desk.post(f"/tickets/{t['id']}/comments", {"visibility": "public", "body": "On it"}, desk.agent))
    desk.ok(
        desk.post(
            f"/tickets/{t['id']}/links", {"module": "maintenance", "entity": "ticket", "ref_id": "w9"}, desk.agent
        )
    )
    mine = desk.ok(desk.get(f"/me/tickets/{t['id']}", desk.requester))
    assert [c["body"] for c in mine["comments"]] == ["On it"]
    assert "links" not in mine


def test_my_tickets_filter_by_status(desk):
    open_one = desk.raise_ticket("Open")
    done = desk.raise_ticket("Done")
    desk.ok(desk.post(f"/tickets/{done['id']}/resolve", {"resolution_note": "Fixed"}, desk.agent))
    assert [t["id"] for t in desk.ok(desk.get("/me/tickets?status=new", desk.requester))["items"]] == [open_one["id"]]


def test_confirm_needs_a_resolved_ticket(desk):
    t = desk.raise_ticket()
    r = desk.post(f"/me/tickets/{t['id']}/confirm", {}, desk.requester)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "transition_not_allowed")


def test_confirm_without_a_body_closes_with_no_rating(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Fixed"}, desk.agent))
    closed = desk.ok(desk.client.post(f"/api/v1/helpdesk/me/tickets/{t['id']}/confirm", headers=desk.requester))
    assert (closed["status"], closed["satisfaction_rating"]) == ("closed", None)


def test_a_rating_outside_one_to_five_is_refused(desk):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Fixed"}, desk.agent))
    assert desk.post(f"/me/tickets/{t['id']}/confirm", {"satisfaction_rating": 6}, desk.requester).status_code == 422


def test_reopen_inside_the_window_and_not_after(desk, clock):
    t = desk.raise_ticket()
    desk.ok(desk.post(f"/tickets/{t['id']}/assign", {}, desk.agent))
    desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Fixed"}, desk.agent))
    clock.set(NOW + timedelta(days=7))
    reopened = desk.ok(desk.post(f"/me/tickets/{t['id']}/reopen", {"reason": "Broken again"}, desk.requester))
    assert (reopened["status"], reopened["reopen_count"], reopened["assignee_id"]) == ("in_progress", 1, desk.agent_id)
    [event] = outbox("helpdesk.ticket.reopened", desk.org.id)
    assert (event["reopen_count"], event["assignee_id"]) == (1, desk.agent_id)
    assert ("ticket.reopened", "Broken again") in audit(desk.org.id, t["id"])

    desk.ok(desk.post(f"/tickets/{t['id']}/resolve", {"resolution_note": "Fixed again"}, desk.agent))
    clock.set(NOW + timedelta(days=15))
    assert desk.ok(desk.get(f"/me/tickets/{t['id']}", desk.requester))["can_reopen"] is False
    r = desk.post(f"/me/tickets/{t['id']}/reopen", {"reason": "Still broken"}, desk.requester)
    assert (r.status_code, r.json()["detail"]["code"]) == (409, "reopen_window_passed")


def test_withdraw_before_resolution(desk):
    t = desk.raise_ticket()
    withdrawn = desk.ok(desk.post(f"/me/tickets/{t['id']}/withdraw", {"reason": "Sorted it myself"}, desk.requester))
    assert withdrawn["status"] == "cancelled"
    [event] = outbox("helpdesk.ticket.cancelled", desk.org.id)
    assert (event["cancelled_by"], event["duplicate_of"]) == (desk.requester_id, None)
    assert ("ticket.withdrawn", "Sorted it myself") in audit(desk.org.id, t["id"])
    assert desk.post(f"/me/tickets/{t['id']}/withdraw", {"reason": "Again"}, desk.requester).status_code == 409


def test_reasons_need_three_characters(desk):
    t = desk.raise_ticket()
    assert desk.post(f"/me/tickets/{t['id']}/withdraw", {"reason": "no"}, desk.requester).status_code == 422


def test_without_a_token_the_caller_is_unauthenticated(desk):
    assert desk.client.get("/api/v1/helpdesk/me/tickets").status_code == 401
    assert desk.client.get("/api/v1/helpdesk/me/tickets", headers={"Authorization": "Bearer nope"}).status_code == 401
