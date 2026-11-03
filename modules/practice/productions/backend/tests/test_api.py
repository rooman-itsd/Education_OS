"""The HTTP surface in contracts/openapi.yaml, end to end against a throwaway SQLite database."""

from conftest import BASE, COORDINATOR, LEAD, MEMBER, NOW, days, make_production
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from sqlalchemy import select


def events_for(production_id: str) -> list[str]:
    """Event names the module published for one production, in order (the transactional outbox)."""
    with SessionLocal() as db:
        rows = db.scalars(select(OutboxEvent).order_by(OutboxEvent.occurred_at, OutboxEvent.id)).all()
    return [r.name for r in rows if (r.payload or {}).get("production_id") == production_id]


# ---------------------------------------------------------------- creating


def test_a_coordinator_creates_a_production_in_planning(client, org):
    _, coordinator = org.user(COORDINATOR)
    r = client.post(
        f"{BASE}/productions",
        json={"title": "Twelfth Night", "kind": "performance", "department": "Drama"},
        headers=coordinator,
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "planned"
    assert body["organisation_id"] == org.id
    assert body["counts"] == {
        "cast_invited": 0,
        "cast_confirmed": 0,
        "cast_declined": 0,
        "tasks_open": 0,
        "tasks_total": 0,
    }
    assert events_for(body["id"]) == ["productions.production.created"]


def test_a_production_created_with_dates_is_scheduled_at_once(client, org):
    _, coordinator = org.user(COORDINATOR)
    body = make_production(client, coordinator, starts_at=days(30), ends_at=days(30.1))
    assert body["status"] == "scheduled"
    assert body["call_time"] is not None  # filled from PRODUCTIONS_DEFAULT_CALL_MINUTES
    assert events_for(body["id"]) == ["productions.production.created", "productions.production.scheduled"]


def test_a_repeated_client_token_returns_the_first_production_instead_of_a_second(client, org):
    _, coordinator = org.user(COORDINATOR)
    first = client.post(
        f"{BASE}/productions",
        json={"title": "Recital", "kind": "recital", "client_token": "token-1"},
        headers=coordinator,
    )
    again = client.post(
        f"{BASE}/productions",
        json={"title": "Recital", "kind": "recital", "client_token": "token-1"},
        headers=coordinator,
    )
    assert first.status_code == 201
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]


def test_another_caller_reusing_the_same_token_gets_their_own_production(client, org):
    """#317's audit found a shared client_token handing one user another user's row. The key is per caller."""
    _, one = org.user(COORDINATOR)
    _, two = org.user(COORDINATOR)
    mine = client.post(
        f"{BASE}/productions", json={"title": "Mine", "kind": "other", "client_token": "shared"}, headers=one
    )
    theirs = client.post(
        f"{BASE}/productions", json={"title": "Theirs", "kind": "other", "client_token": "shared"}, headers=two
    )
    assert mine.status_code == 201 and theirs.status_code == 201
    assert mine.json()["id"] != theirs.json()["id"]
    assert theirs.json()["title"] == "Theirs"


def test_a_member_cannot_create_or_edit_a_production(client, org):
    _, member = org.user(MEMBER)
    assert client.post(f"{BASE}/productions", json={"title": "X", "kind": "other"}, headers=member).status_code == 403
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator)
    assert (
        client.patch(f"{BASE}/productions/{production['id']}", json={"title": "Y"}, headers=member).status_code == 403
    )
    assert client.get(f"{BASE}/productions/{production['id']}", headers=member).status_code == 200


def test_half_a_schedule_is_refused_before_it_reaches_the_service(client, org):
    _, coordinator = org.user(COORDINATOR)
    r = client.post(
        f"{BASE}/productions", json={"title": "X", "kind": "other", "starts_at": days(2)}, headers=coordinator
    )
    assert r.status_code == 422


def test_an_unknown_kind_is_refused(client, org):
    _, coordinator = org.user(COORDINATOR)
    r = client.post(f"{BASE}/productions", json={"title": "X", "kind": "concert"}, headers=coordinator)
    assert r.status_code == 422


# ---------------------------------------------------------------- the life of a production


def test_planning_to_preparation_to_scheduled_to_completed(client, org):
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator, title="Degree Show", kind="exhibition")
    pid = production["id"]

    assert client.post(f"{BASE}/productions/{pid}/complete", headers=coordinator).status_code == 409

    prepared = client.post(f"{BASE}/productions/{pid}/preparation", headers=coordinator)
    assert prepared.status_code == 200
    assert prepared.json()["status"] == "in_preparation"
    assert client.post(f"{BASE}/productions/{pid}/preparation", headers=coordinator).status_code == 409

    scheduled = client.post(
        f"{BASE}/productions/{pid}/schedule",
        json={"starts_at": days(30), "ends_at": days(31), "venue": "Main Hall"},
        headers=coordinator,
    )
    assert scheduled.status_code == 200, scheduled.text
    assert scheduled.json()["status"] == "scheduled"
    assert scheduled.json()["venue"] == "Main Hall"
    assert scheduled.json()["warnings"] == []

    done = client.post(f"{BASE}/productions/{pid}/complete", headers=coordinator)
    assert done.status_code == 200
    assert done.json()["completed_at"] == NOW.isoformat()
    # Nothing touches it afterwards.
    assert client.patch(f"{BASE}/productions/{pid}", json={"title": "No"}, headers=coordinator).status_code == 409
    assert client.post(f"{BASE}/productions/{pid}/cancel", json={}, headers=coordinator).status_code == 409
    assert events_for(pid)[-1] == "productions.production.completed"


def test_scheduling_inside_the_preparation_window_warns_but_goes_ahead(client, org):
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator)
    r = client.post(
        f"{BASE}/productions/{production['id']}/schedule",
        json={"starts_at": days(2), "ends_at": days(2.1)},
        headers=coordinator,
    )
    assert r.status_code == 200
    assert r.json()["status"] == "scheduled"
    assert "days to prepare" in r.json()["warnings"][0]


def test_impossible_dates_are_refused(client, org):
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator)
    r = client.post(
        f"{BASE}/productions/{production['id']}/schedule",
        json={"starts_at": days(10), "ends_at": days(9)},
        headers=coordinator,
    )
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_dates"
    late_call = client.post(
        f"{BASE}/productions/{production['id']}/schedule",
        json={"starts_at": days(10), "ends_at": days(10.2), "call_time": days(10.1)},
        headers=coordinator,
    )
    assert late_call.status_code == 422
    assert late_call.json()["detail"]["code"] == "invalid_call_time"


def test_moving_a_scheduled_production_records_where_it_came_from(client, org):
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator, starts_at=days(20), ends_at=days(20.2))
    moved = client.post(
        f"{BASE}/productions/{production['id']}/schedule",
        json={"starts_at": days(25), "ends_at": days(25.2)},
        headers=coordinator,
    )
    assert moved.status_code == 200
    with SessionLocal() as db:
        rows = db.scalars(select(OutboxEvent).where(OutboxEvent.name == "productions.production.scheduled")).all()
    moves = [r for r in rows if r.payload.get("production_id") == production["id"]]
    assert len(moves) == 2
    assert moves[0].payload["from_starts_at"] is None  # the first schedule came from nowhere
    assert moves[-1].payload["from_starts_at"] is not None  # the move says where it was


def test_an_edit_lists_only_what_really_changed(client, org):
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator, department="Drama")
    r = client.patch(
        f"{BASE}/productions/{production['id']}",
        json={"title": "Twelfth Night", "department": "Theatre"},  # the title is unchanged
        headers=coordinator,
    )
    assert r.status_code == 200
    assert r.json()["department"] == "Theatre"
    with SessionLocal() as db:
        rows = db.scalars(select(OutboxEvent).where(OutboxEvent.name == "productions.production.updated")).all()
    mine = [r for r in rows if r.payload.get("production_id") == production["id"]]
    assert mine[-1].payload["changed"] == ["department"]


def test_a_patch_clears_an_optional_field_but_refuses_to_empty_a_required_one(client, org):
    """Review of #454: `{"kind": null}` passed the schema, reached the NOT NULL column and became a 500, while
    `{"title": null}` was silently ignored. An optional field can still be cleared; a required one is a 422."""
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator, venue="Studio 2", department="Drama")
    url = f"{BASE}/productions/{production['id']}"

    cleared = client.patch(url, json={"venue": None}, headers=coordinator)
    assert cleared.status_code == 200
    assert cleared.json()["venue"] is None
    assert client.patch(url, json={"department": None}, headers=coordinator).json()["department"] is None

    for field in ("title", "kind", "lead_user_id"):
        r = client.patch(url, json={field: None}, headers=coordinator)
        assert r.status_code == 422, (field, r.status_code)
        assert "cannot be cleared" in r.text, field
    # refused before anything was written
    after = client.get(url, headers=coordinator).json()
    assert after["title"] == "Twelfth Night" and after["kind"] == "performance"
    assert after["lead_user_id"] == production["lead_user_id"]
    # and a real value still goes through
    assert client.patch(url, json={"kind": "recital"}, headers=coordinator).json()["kind"] == "recital"


def test_a_blank_title_or_part_name_is_a_422_not_a_stored_empty_string(client, org):
    """Review of #454: min_length=1 passed "   " and the service then stripped it to "", so create and PATCH stored an
    empty title. Text is now stripped before the length check; padding around a real value is trimmed."""
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    base = {"kind": "performance"}
    for blank in ("   ", "\t\n", ""):
        r = client.post(f"{BASE}/productions", json={**base, "title": blank}, headers=coordinator)
        assert r.status_code == 422, (blank, r.status_code, r.text)

    production = make_production(client, coordinator)
    pid = production["id"]
    url = f"{BASE}/productions/{pid}"
    assert client.patch(url, json={"title": "   "}, headers=coordinator).status_code == 422
    assert client.get(url, headers=coordinator).json()["title"] == "Twelfth Night"  # nothing was written

    assert client.post(f"{BASE}/productions/{pid}/tasks", json={"title": "  "}, headers=lead).status_code == 422
    role = {"user_id": "u-1", "role_name": "   ", "kind": "cast"}
    assert client.post(f"{BASE}/productions/{pid}/roles", json=role, headers=lead).status_code == 422

    # padding around a real value is trimmed, not rejected
    assert client.patch(url, json={"title": "  Hamlet  "}, headers=coordinator).json()["title"] == "Hamlet"
    created = client.post(f"{BASE}/productions", json={**base, "title": "  Macbeth "}, headers=coordinator)
    assert created.status_code == 201 and created.json()["title"] == "Macbeth"


def test_a_patch_that_sends_nothing_changes_nothing(client, org):
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator)
    r = client.patch(f"{BASE}/productions/{production['id']}", json={}, headers=coordinator)
    assert r.status_code == 200
    assert r.json()["title"] == production["title"] and r.json()["kind"] == production["kind"]


# ---------------------------------------------------------------- cast and crew


def test_offering_a_part_twice_is_the_same_offer(client, org):
    lead_id, lead = org.user(LEAD)
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator)
    body = {"user_id": "u-1", "role_name": "Viola", "kind": "cast"}
    first = client.post(f"{BASE}/productions/{production['id']}/roles", json=body, headers=lead)
    again = client.post(f"{BASE}/productions/{production['id']}/roles", json=body, headers=lead)
    assert first.status_code == 201, first.text
    assert again.status_code == 200
    assert again.json()["id"] == first.json()["id"]
    assert first.json()["status"] == "invited"
    assert lead_id  # the lead is the assigner; identity of the person cast is a plain user id


def test_only_the_person_offered_a_part_may_answer_it(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    performer_id, performer = org.user(MEMBER)
    _, someone_else = org.user(MEMBER)
    production = make_production(client, coordinator)
    role = client.post(
        f"{BASE}/productions/{production['id']}/roles",
        json={"user_id": performer_id, "role_name": "Viola"},
        headers=lead,
    ).json()

    wrong = client.post(f"{BASE}/roles/{role['id']}/respond", json={"decision": "accept"}, headers=someone_else)
    assert wrong.status_code == 403
    assert wrong.json()["detail"]["code"] == "forbidden"

    accepted = client.post(f"{BASE}/roles/{role['id']}/respond", json={"decision": "accept"}, headers=performer)
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "confirmed"
    assert accepted.json()["responded_at"] == NOW.isoformat()

    twice = client.post(f"{BASE}/roles/{role['id']}/respond", json={"decision": "decline"}, headers=performer)
    assert twice.status_code == 409
    assert twice.json()["detail"]["code"] == "already_answered"
    assert events_for(production["id"])[-1] == "productions.role.accepted"


def test_declining_keeps_the_reason_and_re_offering_opens_the_part_again(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    performer_id, performer = org.user(MEMBER)
    production = make_production(client, coordinator)
    body = {"user_id": performer_id, "role_name": "Malvolio"}
    role = client.post(f"{BASE}/productions/{production['id']}/roles", json=body, headers=lead).json()

    declined = client.post(
        f"{BASE}/roles/{role['id']}/respond", json={"decision": "decline", "reason": "exams"}, headers=performer
    )
    assert declined.json()["status"] == "declined"
    assert declined.json()["reason"] == "exams"

    reopened = client.post(f"{BASE}/productions/{production['id']}/roles", json=body, headers=lead)
    assert reopened.status_code == 201
    assert reopened.json()["id"] == role["id"]
    assert reopened.json()["status"] == "invited"
    assert reopened.json()["reason"] is None


def test_a_lead_withdraws_an_assignment(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    performer_id, performer = org.user(MEMBER)
    production = make_production(client, coordinator)
    role = client.post(
        f"{BASE}/productions/{production['id']}/roles",
        json={"user_id": performer_id, "role_name": "Feste"},
        headers=lead,
    ).json()

    assert client.request("DELETE", f"{BASE}/roles/{role['id']}", json={}, headers=performer).status_code == 403
    gone = client.request("DELETE", f"{BASE}/roles/{role['id']}", json={"reason": "recast"}, headers=lead)
    assert gone.status_code == 200
    assert gone.json()["status"] == "withdrawn"
    assert gone.json()["reason"] == "recast"
    assert client.request("DELETE", f"{BASE}/roles/{role['id']}", json={}, headers=lead).status_code == 409
    assert (
        client.post(f"{BASE}/roles/{role['id']}/respond", json={"decision": "accept"}, headers=performer).status_code
        == 409
    )


def test_cancelling_a_production_withdraws_the_parts_people_hold(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    a_id, a = org.user(MEMBER)
    b_id, _b = org.user(MEMBER)
    production = make_production(client, coordinator)
    pid = production["id"]
    role_a = client.post(
        f"{BASE}/productions/{pid}/roles", json={"user_id": a_id, "role_name": "Olivia"}, headers=lead
    ).json()
    client.post(f"{BASE}/productions/{pid}/roles", json={"user_id": b_id, "role_name": "Orsino"}, headers=lead)
    client.post(f"{BASE}/roles/{role_a['id']}/respond", json={"decision": "accept"}, headers=a)

    cancelled = client.post(f"{BASE}/productions/{pid}/cancel", json={"reason": "hall flooded"}, headers=coordinator)
    assert cancelled.status_code == 200
    assert cancelled.json()["cancelled_reason"] == "hall flooded"
    roles = client.get(f"{BASE}/productions/{pid}/roles", headers=coordinator).json()
    assert {r["status"] for r in roles} == {"withdrawn"}
    assert all(r["reason"] == "hall flooded" for r in roles)
    names = events_for(pid)
    assert names.count("productions.role.withdrawn") == 2
    assert names[-1] == "productions.production.cancelled"
    # Nobody can be cast onto it afterwards.
    assert (
        client.post(
            f"{BASE}/productions/{pid}/roles", json={"user_id": a_id, "role_name": "Maria"}, headers=lead
        ).status_code
        == 409
    )


# ---------------------------------------------------------------- preparation tasks


def test_a_task_cannot_be_completed_once_its_production_is_cancelled(client, org):
    """Review of #454 (follow-up): complete_task used to ignore the production's status."""
    _, coordinator = org.user(COORDINATOR)
    production = make_production(client, coordinator)
    pid = production["id"]
    task = client.post(f"{BASE}/productions/{pid}/tasks", json={"title": "Hire lights"}, headers=coordinator).json()
    assert client.post(f"{BASE}/productions/{pid}/cancel", json={}, headers=coordinator).status_code == 200

    refused = client.post(f"{BASE}/tasks/{task['id']}/complete", headers=coordinator)
    assert refused.status_code == 409, refused.text
    assert "wrong_status" in refused.text
    open_tasks = client.get(f"{BASE}/productions/{pid}/tasks", headers=coordinator).json()
    assert [t["status"] for t in open_tasks] == ["open"]


def test_tasks_are_added_listed_outstanding_first_and_completed_once(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    _, member = org.user(MEMBER)
    production = make_production(client, coordinator)
    pid = production["id"]

    assert (
        client.post(f"{BASE}/productions/{pid}/tasks", json={"title": "Hire lights"}, headers=member).status_code == 403
    )
    first = client.post(
        f"{BASE}/productions/{pid}/tasks", json={"title": "Hire lights", "due_at": days(5)}, headers=lead
    )
    second = client.post(f"{BASE}/productions/{pid}/tasks", json={"title": "Print programmes"}, headers=lead)
    assert first.status_code == 201 and second.status_code == 201
    assert first.json()["position"] == 1 and second.json()["position"] == 2

    done = client.post(f"{BASE}/tasks/{first.json()['id']}/complete", headers=lead)
    assert done.status_code == 200
    assert done.json()["status"] == "done"
    assert done.json()["completed_at"] == NOW.isoformat()
    assert client.post(f"{BASE}/tasks/{first.json()['id']}/complete", headers=lead).status_code == 200  # idempotent

    tasks = client.get(f"{BASE}/productions/{pid}/tasks", headers=lead).json()
    assert [t["status"] for t in tasks] == ["open", "done"]
    assert client.get(f"{BASE}/productions/{pid}", headers=coordinator).json()["counts"]["tasks_open"] == 1
    with SessionLocal() as db:
        rows = db.scalars(select(OutboxEvent).where(OutboxEvent.name == "productions.task.completed")).all()
    assert [r for r in rows if r.payload["production_id"] == pid][-1].payload["outstanding"] == 1


# ---------------------------------------------------------------- listing and filters


def test_productions_are_listed_with_filters_and_paging(client, org):
    _, coordinator = org.user(COORDINATOR)
    make_production(client, coordinator, title="Jazz Night", kind="performance", department="Music")
    make_production(client, coordinator, title="Degree Show", kind="exhibition", department="Design")
    make_production(client, coordinator, title="Moot Final", kind="competition", starts_at=days(5), ends_at=days(5.2))

    everything = client.get(f"{BASE}/productions", headers=coordinator).json()
    assert everything["total"] == 3
    assert everything["page"] == 1
    assert client.get(f"{BASE}/productions?kind=exhibition", headers=coordinator).json()["total"] == 1
    assert client.get(f"{BASE}/productions?department=Music", headers=coordinator).json()["total"] == 1
    assert client.get(f"{BASE}/productions?status=scheduled", headers=coordinator).json()["total"] == 1
    assert client.get(f"{BASE}/productions?q=jazz", headers=coordinator).json()["total"] == 1
    assert client.get(f"{BASE}/productions", params={"from": days(1)}, headers=coordinator).json()["total"] == 1
    paged = client.get(f"{BASE}/productions?page=2&page_size=2", headers=coordinator).json()
    assert len(paged["items"]) == 1 and paged["total"] == 3


def test_an_unknown_status_filter_is_refused_rather_than_matching_nothing(client, org):
    _, coordinator = org.user(COORDINATOR)
    r = client.get(f"{BASE}/productions?status=postponed", headers=coordinator)
    assert r.status_code == 422
    assert r.json()["detail"]["code"] == "invalid_status"


def test_a_missing_production_is_a_404_not_a_500(client, org):
    _, coordinator = org.user(COORDINATOR)
    assert client.get(f"{BASE}/productions/nope", headers=coordinator).status_code == 404
    assert client.post(f"{BASE}/productions/nope/complete", headers=coordinator).status_code == 404
    assert (
        client.post(f"{BASE}/roles/nope/respond", json={"decision": "accept"}, headers=coordinator).status_code == 404
    )
    assert client.post(f"{BASE}/tasks/nope/complete", headers=coordinator).status_code == 404


def test_an_anonymous_or_unsigned_caller_gets_401(client, org):
    assert client.get(f"{BASE}/productions").status_code == 401
    assert client.get(f"{BASE}/productions", headers={"Authorization": "Bearer nonsense"}).status_code == 401


# ---------------------------------------------------------------- the four dashboard widgets


def test_the_calendar_shows_scheduled_productions_in_the_window_soonest_first(client, org):
    _, coordinator = org.user(COORDINATOR)
    make_production(client, coordinator, title="Later", starts_at=days(40), ends_at=days(40.2))
    make_production(client, coordinator, title="Sooner", starts_at=days(3), ends_at=days(3.2))
    make_production(client, coordinator, title="Planned only")
    make_production(client, coordinator, title="Long past", starts_at=days(-40), ends_at=days(-39.9))

    page = client.get(f"{BASE}/calendar", headers=coordinator).json()
    assert [row["title"] for row in page["items"]] == ["Sooner", "Later"]
    assert page["total"] == 2
    narrow = client.get(f"{BASE}/calendar", params={"from": days(0), "to": days(10)}, headers=coordinator).json()
    assert [row["title"] for row in narrow["items"]] == ["Sooner"]
    assert client.get(f"{BASE}/calendar?limit=1", headers=coordinator).json()["total"] == 2  # total ignores the limit


def test_a_production_already_running_is_still_on_the_calendar(client, org):
    _, coordinator = org.user(COORDINATOR)
    make_production(client, coordinator, title="Running now", starts_at=days(-1), ends_at=days(1))
    titles = [row["title"] for row in client.get(f"{BASE}/calendar", headers=coordinator).json()["items"]]
    assert titles == ["Running now"]


def test_upcoming_counts_the_cast_that_has_confirmed(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    performer_id, performer = org.user(MEMBER)
    production = make_production(client, coordinator, starts_at=days(12), ends_at=days(12.2))
    role = client.post(
        f"{BASE}/productions/{production['id']}/roles",
        json={"user_id": performer_id, "role_name": "Viola"},
        headers=lead,
    ).json()
    assert client.get(f"{BASE}/upcoming", headers=performer).json()["items"][0]["cast_confirmed"] == 0
    client.post(f"{BASE}/roles/{role['id']}/respond", json={"decision": "accept"}, headers=performer)
    assert client.get(f"{BASE}/upcoming", headers=performer).json()["items"][0]["cast_confirmed"] == 1


def test_my_roles_shows_only_the_callers_own_parts(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    mine_id, mine = org.user(MEMBER)
    theirs_id, theirs = org.user(MEMBER)
    production = make_production(client, coordinator, starts_at=days(8), ends_at=days(8.2))
    client.post(
        f"{BASE}/productions/{production['id']}/roles", json={"user_id": mine_id, "role_name": "Viola"}, headers=lead
    )
    client.post(
        f"{BASE}/productions/{production['id']}/roles", json={"user_id": theirs_id, "role_name": "Olivia"}, headers=lead
    )

    page = client.get(f"{BASE}/my-roles", headers=mine).json()
    assert page["total"] == 1
    assert page["items"][0]["role_name"] == "Viola"
    assert page["items"][0]["title"] == "Twelfth Night"
    assert client.get(f"{BASE}/my-roles", headers=theirs).json()["items"][0]["role_name"] == "Olivia"


def test_my_roles_drops_answered_offers_when_asked_and_finished_productions_always(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    performer_id, performer = org.user(MEMBER)
    production = make_production(client, coordinator, starts_at=days(9), ends_at=days(9.2))
    role = client.post(
        f"{BASE}/productions/{production['id']}/roles",
        json={"user_id": performer_id, "role_name": "Viola"},
        headers=lead,
    ).json()
    assert client.get(f"{BASE}/my-roles?open=true", headers=performer).json()["total"] == 1
    client.post(f"{BASE}/roles/{role['id']}/respond", json={"decision": "accept"}, headers=performer)
    assert client.get(f"{BASE}/my-roles?open=true", headers=performer).json()["total"] == 0
    assert client.get(f"{BASE}/my-roles", headers=performer).json()["total"] == 1

    client.post(f"{BASE}/productions/{production['id']}/complete", headers=coordinator)
    assert client.get(f"{BASE}/my-roles", headers=performer).json()["total"] == 0


def test_in_preparation_puts_the_most_pressing_production_first(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    calm = make_production(client, coordinator, title="Calm")
    pressing = make_production(client, coordinator, title="Pressing")
    client.post(f"{BASE}/productions/{calm['id']}/tasks", json={"title": "Later", "due_at": days(20)}, headers=lead)
    client.post(
        f"{BASE}/productions/{pressing['id']}/tasks", json={"title": "Overdue", "due_at": days(-2)}, headers=lead
    )
    client.post(f"{BASE}/productions/{pressing['id']}/tasks", json={"title": "Also open"}, headers=lead)

    page = client.get(f"{BASE}/in-preparation", headers=lead).json()
    assert [row["title"] for row in page["items"]] == ["Pressing", "Calm"]
    top = page["items"][0]
    assert top["tasks_open"] == 2 and top["tasks_total"] == 2 and top["tasks_overdue"] == 1
    assert top["next_task_due_at"] is not None
    assert page["items"][1]["tasks_overdue"] == 0


def test_in_preparation_counts_invitations_nobody_has_answered(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    performer_id, performer = org.user(MEMBER)
    production = make_production(client, coordinator)
    role = client.post(
        f"{BASE}/productions/{production['id']}/roles",
        json={"user_id": performer_id, "role_name": "Viola"},
        headers=lead,
    ).json()
    assert client.get(f"{BASE}/in-preparation", headers=lead).json()["items"][0]["cast_unanswered"] == 1
    client.post(f"{BASE}/roles/{role['id']}/respond", json={"decision": "accept"}, headers=performer)
    assert client.get(f"{BASE}/in-preparation", headers=lead).json()["items"][0]["cast_unanswered"] == 0


def test_in_preparation_can_be_narrowed_to_the_callers_own_productions(client, org):
    _, coordinator = org.user(COORDINATOR)
    lead_id, lead = org.user(LEAD)
    make_production(client, coordinator, title="Somebody else's")
    make_production(client, coordinator, title="Mine", lead_user_id=lead_id)

    everything = client.get(f"{BASE}/in-preparation", headers=lead).json()
    assert {row["title"] for row in everything["items"]} == {"Somebody else's", "Mine"}
    mine = client.get(f"{BASE}/in-preparation?mine=true", headers=lead).json()
    assert [row["title"] for row in mine["items"]] == ["Mine"]


def test_a_scheduled_production_leaves_the_in_preparation_list(client, org):
    _, coordinator = org.user(COORDINATOR)
    _, lead = org.user(LEAD)
    production = make_production(client, coordinator)
    assert client.get(f"{BASE}/in-preparation", headers=lead).json()["total"] == 1
    client.post(
        f"{BASE}/productions/{production['id']}/schedule",
        json={"starts_at": days(30), "ends_at": days(30.2)},
        headers=coordinator,
    )
    assert client.get(f"{BASE}/in-preparation", headers=lead).json()["total"] == 0
    assert client.get(f"{BASE}/calendar", headers=lead).json()["total"] == 1


def test_each_widget_endpoint_refuses_a_caller_without_its_key(client, org):
    _, member = org.user(MEMBER)
    _, nobody = org.user("student")
    assert client.get(f"{BASE}/in-preparation", headers=member).status_code == 403  # member holds no task:read
    assert client.get(f"{BASE}/my-roles", headers=member).status_code == 200
    for path in ("/calendar", "/upcoming", "/my-roles", "/in-preparation"):
        assert client.get(f"{BASE}{path}", headers=nobody).status_code == 403
