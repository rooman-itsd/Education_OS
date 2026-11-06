"""Corrective actions through the HTTP API: assign, change, the owner marking their own action done, overdue worked
out when read, and GET /actions."""

from datetime import timedelta

from conftest import NOW, audit, days, outbox

WORK_ORDER = {"module": "maintenance", "entity": "ticket", "id": "mt-12", "relation": "work_order"}


def test_add_an_action_with_an_event(desk):
    problem = desk.problem()
    action = desk.action(problem["id"], reference=WORK_ORDER)
    assert (action["status"], action["owner_id"], action["due_date"], action["overdue"]) == (
        "open",
        desk.responder_id,
        days(7),
        False,
    )
    assert (action["reference"], action["completed_at"]) == ({**WORK_ORDER, "note": None}, None)
    assert outbox("incident-management.action.assigned", desk.org.id) == [
        {
            "organisation_id": desk.org.id,
            "action_id": action["id"],
            "problem_id": problem["id"],
            "problem_number": problem["number"],
            "owner_id": desk.responder_id,
            "due_date": days(7),
        }
    ]
    assert audit(desk.org.id, action["id"]) == [("action.created", None)]
    past = desk.post(
        f"/problems/{problem['id']}/actions",
        {"description": "Too late", "owner_id": desk.responder_id, "due_date": days(-1)},
    )
    assert (past.status_code, past.json()["detail"]["code"]) == (422, "due_date_in_past")


def test_change_owner_due_date_and_reference(desk):
    problem = desk.problem()
    action = desk.action(problem["id"], reference=WORK_ORDER)
    path = f"/problems/{problem['id']}/actions/{action['id']}"
    changed = desk.ok(desk.patch(path, {"owner_id": desk.manager_id, "due_date": days(14), "reference": None}))
    assert (changed["owner_id"], changed["due_date"], changed["reference"]) == (desk.manager_id, days(14), None)
    assert [e["owner_id"] for e in outbox("incident-management.action.assigned", desk.org.id)] == [
        desk.responder_id,
        desk.manager_id,
    ]
    desk.ok(desk.patch(path, {"owner_id": desk.manager_id}))  # same owner: no new event
    assert len(outbox("incident-management.action.assigned", desk.org.id)) == 2
    assert audit(desk.org.id, action["id"])[-1] == ("action.updated", "fields: due_date, owner_id, reference")
    assert desk.patch(path, {"due_date": days(-2)}).status_code == 422


def test_owner_marks_their_own_action_done_with_read_only(desk, clock):
    problem = desk.problem()
    action = desk.action(problem["id"])
    path = f"/problems/{problem['id']}/actions/{action['id']}"
    for body in ({"status": "cancelled"}, {"status": "done", "description": "Changed too"}, {"due_date": days(9)}):
        refused = desk.patch(path, body, desk.responder)
        assert (refused.status_code, refused.json()["detail"]["code"]) == (403, "forbidden"), body
    _, stranger = desk.org.user("incident-management-responder")
    assert desk.patch(path, {"status": "done"}, stranger).status_code == 403  # not their action
    assert desk.patch(path, {"status": "done"}, desk.viewer).status_code == 403
    clock.set(NOW + timedelta(hours=5))
    done = desk.ok(desk.patch(path, {"status": "done"}, desk.responder))
    assert (done["status"], done["completed_at"], done["overdue"]) == ("done", "2026-11-04T14:00:00+00:00", False)
    again = desk.patch(path, {"status": "cancelled"})
    assert (again.status_code, again.json()["detail"]["code"]) == (409, "action_closed")
    assert audit(desk.org.id, action["id"])[-1] == ("action.done", None)


def test_cancel_records_no_completion(desk):
    problem = desk.problem()
    action = desk.action(problem["id"])
    cancelled = desk.ok(desk.patch(f"/problems/{problem['id']}/actions/{action['id']}", {"status": "cancelled"}))
    assert (cancelled["status"], cancelled["completed_at"]) == ("cancelled", None)


def test_action_of_another_problem_is_not_found(desk):
    one, two = desk.problem(), desk.problem()
    action = desk.action(one["id"])
    assert desk.patch(f"/problems/{two['id']}/actions/{action['id']}", {"status": "done"}).status_code == 404


def test_closed_problem_takes_no_new_actions_but_open_ones_can_finish(desk):
    problem = desk.problem()
    action = desk.action(problem["id"])
    path = f"/problems/{problem['id']}"
    desk.ok(desk.post(f"{path}/status", {"status": "investigating"}))
    desk.published(problem["id"])
    desk.ok(desk.post(f"{path}/status", {"status": "resolved"}))
    desk.ok(desk.post(f"{path}/status", {"status": "closed"}))
    body = {"description": "Late action", "owner_id": desk.responder_id, "due_date": days(3)}
    refused = desk.post(f"{path}/actions", body)
    assert (refused.status_code, refused.json()["detail"]["code"]) == (409, "problem_closed")
    assert desk.ok(desk.patch(f"{path}/actions/{action['id']}", {"status": "done"}, desk.responder))["status"] == "done"


def test_overdue_is_worked_out_when_read_and_listed(desk, clock):
    problem = desk.problem()
    soon = desk.action(problem["id"], due_date=days(1))
    later = desk.action(problem["id"], due_date=days(10), owner_id=desk.manager_id)
    finished = desk.action(problem["id"], due_date=days(0))
    desk.ok(desk.patch(f"/problems/{problem['id']}/actions/{finished['id']}", {"status": "done"}))
    clock.set(NOW + timedelta(days=3))

    def listed(query: str, headers=None) -> list[tuple[str, bool]]:
        items = desk.ok(desk.get(f"/actions{query}", headers or desk.viewer))["items"]
        return [(a["id"], a["overdue"]) for a in items]

    assert listed("") == [(finished["id"], False), (soon["id"], True), (later["id"], False)]  # soonest due first
    assert listed("?overdue=true") == [(soon["id"], True)]
    assert listed("?overdue=false") == [(finished["id"], False), (later["id"], False)]
    assert listed("?status=open") == [(soon["id"], True), (later["id"], False)]
    assert listed("?owner=me", desk.responder) == [(finished["id"], False), (soon["id"], True)]
    assert listed(f"?owner={desk.manager_id}") == [(later["id"], False)]
    page = desk.ok(desk.get("/actions?limit=1"))
    assert page["next_cursor"] is not None
    assert desk.get("/actions?status=open,done").status_code == 422
