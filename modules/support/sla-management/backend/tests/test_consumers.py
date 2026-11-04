"""The helpdesk event consumers: every handler, the clock moves they drive, duplicate delivery, another
organisation's ids, malformed payloads and registration. Events go through the handlers (conftest.deliver)."""

import tomllib
from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from conftest import CATEGORY, LEAD, NOW, OTHER_CATEGORY, FakeEvent, at, audit, deliver, new_uuid, outbox
from eos_sla_management.application import consumers
from eos_sla_management.application.consumers import CONSUMERS

MODULE = Path(__file__).resolve().parents[2]
HELPDESK_EVENTS = MODULE.parent / "helpdesk" / "contracts" / "events.yaml"
STARTED, STOPPED = "sla-management.clock.started", "sla-management.clock.stopped"


def iso(minutes: int) -> str:
    return (NOW + timedelta(minutes=minutes)).isoformat()


def names(org_id: str, *events: str) -> dict[str, int]:
    return {e: len(outbox(f"sla-management.clock.{e}", org_id)) for e in events}


def status(desk, ticket_id: str, to_status: str, minutes: int, hold_reason: str | None = None) -> str:
    return desk.send(
        "status-changed",
        {
            "organisation_id": desk.org.id,
            "ticket_id": ticket_id,
            "number": "HD-1",
            "from_status": "in_progress",
            "to_status": to_status,
            "hold_reason": hold_reason,
            "changed_at": at(minutes),
        },
    )


def simple(desk, name: str, ticket_id: str, minutes: int, **extra) -> str:
    field = {"responded": "responded_at", "resolved": "resolved_at", "closed": "closed_at"}.get(name, f"{name}_at")
    return desk.send(
        name, {"organisation_id": desk.org.id, "ticket_id": ticket_id, "number": "HD-1", field: at(minutes), **extra}
    )


# ---------------------------------------------------------------- registration


def test_the_consumers_are_the_manifest_events_and_the_entry_point():
    manifest = yaml.safe_load((MODULE / "module.yaml").read_text(encoding="utf-8"))
    assert set(CONSUMERS) == set(manifest["consumes_events"])
    assert len(CONSUMERS) == 9
    project = tomllib.loads((MODULE / "backend" / "pyproject.toml").read_text(encoding="utf-8"))
    entry = project["project"]["entry-points"]["eos.event_consumers"]
    assert entry == {"sla-management": "eos_sla_management.application.consumers:CONSUMERS"}
    assert all(callable(handler) for handler in CONSUMERS.values())


def test_the_handlers_read_only_fields_helpdesk_publishes():
    if not HELPDESK_EVENTS.exists():
        pytest.skip("the helpdesk contract is not in this checkout")
    published = {e["name"]: set(e["payload"]) for e in yaml.safe_load(HELPDESK_EVENTS.read_text("utf-8"))["events"]}
    read = {
        consumers.CREATED: {"ticket_id", "number", "category_id", "queue_id", "priority", "created_at"},
        consumers.ASSIGNED: {"ticket_id", "queue_id", "assignee_id"},
        consumers.RESPONDED: {"ticket_id", "responded_at"},
        consumers.STATUS_CHANGED: {"ticket_id", "to_status", "hold_reason", "changed_at"},
        consumers.RECLASSIFIED: {"ticket_id", "category_id", "priority"},
        consumers.RESOLVED: {"ticket_id", "resolved_at"},
        consumers.REOPENED: {"ticket_id", "assignee_id", "reopened_at"},
        consumers.CLOSED: {"ticket_id", "closed_at"},
        consumers.CANCELLED: {"ticket_id", "cancelled_at"},
    }
    assert set(read) == set(CONSUMERS)
    for name, fields in read.items():
        assert fields <= published[name], (name, fields - published[name])
    # and nothing else: the source names every payload key the handlers look up
    import inspect

    source = inspect.getsource(consumers)
    for key in ("requester_id", "raised_by_id", "satisfaction_rating", "duplicate_of", "responded_by"):
        assert f'"{key}"' not in source


# ---------------------------------------------------------------- created


def test_created_starts_both_clocks_under_the_policy(desk):
    policy = desk.policy()
    ticket = desk.ticket(number="HD-000123")
    clocks = desk.clocks(ticket)
    response, resolution = clocks["response"], clocks["resolution"]
    assert (response["state"], response["target_minutes"], response["policy_id"]) == ("running", 60, policy["id"])
    assert (response["warn_at"], response["due_at"]) == (iso(30), iso(60))
    assert (resolution["warn_at"], resolution["due_at"], resolution["target_minutes"]) == (iso(120), iso(240), 240)
    assert response["ticket_number"] == "HD-000123"
    assert (response["priority"], response["category_id"]) == ("high", CATEGORY)
    started = {p["kind"]: p for p in outbox(STARTED, desk.org.id)}
    assert set(started) == {"response", "resolution"}
    assert started["response"]["due_at"] == iso(60) and started["response"]["organisation_id"] == desk.org.id
    assert audit(desk.org.id, response["id"]) == ["clock.started"]


def test_no_matching_policy_leaves_the_ticket_untracked(desk):
    desk.policy(priority="urgent")
    ticket = desk.ticket(priority="low")
    assert desk.get(f"/tickets/{ticket}", desk.viewer).status_code == 404
    assert outbox(STARTED, desk.org.id) == []
    assert simple(desk, "responded", ticket, 5, responded_by=new_uuid()) == "ignored"


def test_the_category_policy_wins_over_every_category(desk):
    cal = desk.calendar()["id"]
    desk.policy(cal, name="Every category")
    specific = desk.policy(cal, name="Network", category_id=CATEGORY, response_target_minutes=15)
    assert desk.clocks(desk.ticket())["response"]["policy_id"] == specific["id"]
    other = desk.clocks(desk.ticket(category_id=OTHER_CATEGORY))["response"]
    assert other["target_minutes"] == 60


def test_business_hours_set_the_due_time(desk):
    cal = desk.calendar(always_open=False, working_hours=[{"weekday": 1, "start": "09:00", "end": "09:30"}])
    desk.policy(cal["id"], response_target_minutes=60, resolution_target_minutes=60)
    clocks = desk.clocks(desk.ticket())
    assert clocks["response"]["due_at"] == (NOW + timedelta(days=7, minutes=30)).isoformat()  # 30 min each Monday


# ---------------------------------------------------------------- responded and warnings


def test_response_in_time_is_met(desk):
    desk.policy()
    ticket = desk.ticket()
    assert simple(desk, "responded", ticket, 20, responded_by=new_uuid()) == "applied"
    response = desk.clocks(ticket)["response"]
    assert (response["state"], response["outcome"], response["business_minutes_used"]) == ("stopped", "met", 20)
    assert response["stopped_at"] == iso(20) and response["breached"] is False
    assert outbox(STOPPED, desk.org.id)[-1] == {
        "organisation_id": desk.org.id,
        "clock_id": response["id"],
        "ticket_id": ticket,
        "kind": "response",
        "outcome": "met",
        "stopped_at": iso(20),
        "business_minutes_used": 20,
    }
    assert desk.clocks(ticket)["resolution"]["state"] == "running"


def test_late_response_records_warning_breach_and_escalations_first(desk):
    desk.policy()
    ticket = desk.ticket()
    desk.assign(ticket, desk.agent_id)
    simple(desk, "responded", ticket, 130, responded_by=new_uuid())
    response = desk.clocks(ticket)["response"]
    assert (response["outcome"], response["breached"], response["breached_at"]) == ("breached", True, iso(60))
    assert response["warned"] is True
    warning = outbox("sla-management.clock.warning-raised", desk.org.id)
    breach = outbox("sla-management.clock.breached", desk.org.id)
    assert [w["assignee_id"] for w in warning] == [desk.agent_id, desk.agent_id]  # both clocks passed 30 / 120
    assert [b["kind"] for b in breach] == ["response"]  # resolution (240) not yet due at 130
    assert breach[0]["breached_at"] == iso(60)
    escalated = outbox("sla-management.clock.escalated", desk.org.id)
    assert sorted((e["level"], e["recipient_ids"], e["escalated_at"]) for e in escalated) == [
        (1, [desk.agent_id], iso(60)),
        (2, [LEAD], iso(120)),
    ]
    detail = desk.ok(desk.get(f"/clocks/{response['id']}", desk.viewer))
    assert [(e["level"], e["sent_at"]) for e in detail["escalations"]] == [(1, iso(60)), (2, iso(120))]
    assert audit(desk.org.id, response["id"]) == [
        "clock.started",
        "clock.warning_raised",
        "clock.breached",
        "clock.escalated",
        "clock.escalated",
        "clock.stopped",
    ]


def test_check_due_clocks_publishes_once(desk, clock):
    from eos_core.db import SessionLocal
    from eos_core.tenant import organisation_scope
    from eos_sla_management.application.service import check_due_clocks

    desk.policy()
    ticket = desk.ticket()

    def check(minutes: int) -> int:
        clock.set(NOW + timedelta(minutes=minutes))
        with organisation_scope(desk.org.id), SessionLocal() as db:
            return check_due_clocks(db, desk.org.id)

    assert check(10) == 0
    assert check(35) == 1  # the response warning
    assert names(desk.org.id, "warning-raised", "breached", "escalated") == {
        "warning-raised": 1,
        "breached": 0,
        "escalated": 0,
    }
    check(61)
    check(61)
    assert names(desk.org.id, "breached", "escalated") == {"breached": 1, "escalated": 1}
    check(125)
    assert names(desk.org.id, "warning-raised", "escalated") == {"warning-raised": 2, "escalated": 2}
    assert check(125) == 0
    assert desk.clocks(ticket)["response"]["breached_at"] == iso(60)


def test_a_running_clock_reads_as_breached_once_due(desk, clock):
    desk.policy()
    ticket = desk.ticket()
    clock.set(NOW + timedelta(minutes=45))
    response = desk.clocks(ticket)["response"]
    assert (response["warned"], response["breached"], response["business_minutes_used"]) == (True, False, 45)
    clock.set(NOW + timedelta(minutes=75))
    response = desk.clocks(ticket)["response"]
    assert (response["breached"], response["breached_at"]) == (True, iso(60))
    assert outbox("sla-management.clock.breached", desk.org.id) == []  # recorded when next checked


# ---------------------------------------------------------------- hold, reclassify, resolve, reopen, close, cancel


def test_hold_pauses_and_resumes_with_a_new_due_time(desk):
    desk.policy()
    ticket = desk.ticket()
    status(desk, ticket, "on_hold", 10, "waiting_requester")
    paused = desk.clocks(ticket)
    assert {c["state"] for c in paused.values()} == {"paused"}
    assert paused["resolution"]["due_at"] is None and paused["resolution"]["paused_at"] == iso(10)
    assert paused["resolution"]["business_minutes_used"] == 10
    assert outbox("sla-management.clock.paused", desk.org.id)[-1]["business_minutes_used"] == 10
    status(desk, ticket, "in_progress", 100)
    resumed = desk.clocks(ticket)
    assert resumed["resolution"]["due_at"] == iso(100 + 230)
    assert resumed["response"]["due_at"] == iso(100 + 50)
    [last] = [e for e in outbox("sla-management.clock.resumed", desk.org.id) if e["kind"] == "resolution"]
    assert (last["resumed_at"], last["due_at"]) == (iso(100), iso(330))


def test_a_hold_reason_the_policy_does_not_pause_on_changes_nothing(desk):
    desk.policy()
    ticket = desk.ticket()
    status(desk, ticket, "on_hold", 10, "waiting_internal")
    assert {c["state"] for c in desk.clocks(ticket).values()} == {"running"}
    status(desk, ticket, "on_hold", 20, "waiting_third_party")
    assert {c["state"] for c in desk.clocks(ticket).values()} == {"paused"}
    status(desk, ticket, "on_hold", 30, "waiting_internal")  # held for a reason that does not pause: resumes
    assert {c["state"] for c in desk.clocks(ticket).values()} == {"running"}


def test_reclassified_moves_to_the_new_policy_keeping_time_used(desk):
    cal = desk.calendar()["id"]
    first = desk.policy(cal)
    urgent = desk.policy(
        cal, name="Urgent", priority="urgent", response_target_minutes=30, resolution_target_minutes=120
    )
    ticket = desk.ticket()
    payload = {
        "organisation_id": desk.org.id,
        "ticket_id": ticket,
        "number": "HD-1",
        "category_id": CATEGORY,
        "previous_category_id": CATEGORY,
        "priority": "urgent",
        "previous_priority": "high",
        "changed_by": new_uuid(),
    }
    desk.send("reclassified", payload, occurred_at=NOW + timedelta(minutes=20))
    clocks = desk.clocks(ticket)
    resolution = clocks["resolution"]
    assert (resolution["policy_id"], resolution["target_minutes"], resolution["priority"]) == (
        urgent["id"],
        120,
        "urgent",
    )
    assert resolution["due_at"] == iso(120)  # 20 used, 100 left from minute 20
    [event] = [e for e in outbox("sla-management.clock.recalculated", desk.org.id) if e["kind"] == "resolution"]
    assert (event["previous_policy_id"], event["policy_id"], event["target_minutes"]) == (
        first["id"],
        urgent["id"],
        120,
    )
    # urgent's 30-minute response target is already 20 used: due at minute 30
    assert clocks["response"]["due_at"] == iso(30)


def test_reclassified_without_a_matching_policy_keeps_the_targets(desk):
    desk.policy()
    ticket = desk.ticket()
    payload = {
        "organisation_id": desk.org.id,
        "ticket_id": ticket,
        "number": "HD-1",
        "category_id": None,
        "previous_category_id": CATEGORY,
        "priority": "low",
        "previous_priority": "high",
        "changed_by": None,
    }
    desk.send("reclassified", payload)
    response = desk.clocks(ticket)["response"]
    assert (response["priority"], response["category_id"], response["target_minutes"]) == ("low", None, 60)
    assert outbox("sla-management.clock.recalculated", desk.org.id) == []


def test_resolve_reopen_close(desk):
    desk.policy()
    ticket = desk.ticket()
    simple(desk, "resolved", ticket, 50, requester_id=new_uuid(), resolved_by=new_uuid())
    clocks = desk.clocks(ticket)
    assert {k: (c["state"], c["outcome"]) for k, c in clocks.items()} == {
        "response": ("stopped", "met"),  # resolved without a public reply first stops it too
        "resolution": ("stopped", "met"),
    }
    reopen = {"requester_id": new_uuid(), "assignee_id": desk.agent_id, "reopen_count": 1}
    assert simple(desk, "reopened", ticket, 300, **reopen) == "applied"
    clocks = desk.clocks(ticket)
    resolution = clocks["resolution"]
    assert (resolution["state"], resolution["outcome"], resolution["stopped_at"]) == ("running", None, None)
    assert resolution["due_at"] == iso(300 + 190) and resolution["assignee_id"] == desk.agent_id
    assert clocks["response"]["state"] == "stopped"
    simple(desk, "resolved", ticket, 600, requester_id=new_uuid(), resolved_by=new_uuid())
    resolution = desk.clocks(ticket)["resolution"]
    assert (resolution["outcome"], resolution["business_minutes_used"]) == ("breached", 350)  # met, then late
    simple(desk, "closed", ticket, 700, closed_by=None, satisfaction_rating=None)
    assert simple(desk, "reopened", ticket, 800, **reopen) == "ignored"  # closed is final
    assert desk.clocks(ticket)["resolution"]["state"] == "stopped"


def test_cancelled_cancels_open_clocks_only(desk):
    desk.policy()
    ticket = desk.ticket()
    simple(desk, "responded", ticket, 5, responded_by=new_uuid())
    simple(desk, "cancelled", ticket, 15, cancelled_by=new_uuid(), duplicate_of=None)
    clocks = desk.clocks(ticket)
    assert (clocks["response"]["state"], clocks["response"]["outcome"]) == ("stopped", "met")
    assert (clocks["resolution"]["state"], clocks["resolution"]["outcome"]) == ("cancelled", None)
    cancelled = outbox("sla-management.clock.cancelled", desk.org.id)
    assert [(c["kind"], c["cancelled_at"]) for c in cancelled] == [("resolution", iso(15))]


def test_assignment_before_creation_is_kept(desk, clock):
    desk.policy()
    ticket = new_uuid()
    assert (
        deliver(
            desk.org.id,
            "helpdesk.ticket.assigned",
            {"ticket_id": ticket, "queue_id": None, "assignee_id": desk.agent_id},
        )
        == "applied"
    )
    deliver(
        desk.org.id,
        "helpdesk.ticket.created",
        {
            "ticket_id": ticket,
            "number": "HD-9",
            "category_id": CATEGORY,
            "queue_id": None,
            "priority": "high",
            "created_at": at(0),
        },
    )
    assert desk.clocks(ticket)["response"]["assignee_id"] == desk.agent_id
    clock.set(NOW + timedelta(minutes=90))
    mine = desk.ok(desk.get("/stats/breaches?scope=mine", desk.agent))
    assert (mine["breached_open"], [i["ticket_number"] for i in mine["most_overdue"]]) == (1, ["HD-9"])


def test_an_event_before_the_clock_started_counts_from_the_start(desk):
    desk.policy()
    ticket = desk.ticket(created=30)
    simple(desk, "responded", ticket, 10, responded_by=new_uuid())  # out of order: before created_at
    response = desk.clocks(ticket)["response"]
    assert (response["stopped_at"], response["business_minutes_used"], response["outcome"]) == (iso(30), 0, "met")


# ---------------------------------------------------------------- idempotency and organisations


def test_a_duplicate_delivery_changes_nothing(desk):
    desk.policy()
    ticket = desk.ticket()
    event = FakeEvent(
        name="helpdesk.ticket.responded",
        organisation_id=desk.org.id,
        payload={"ticket_id": ticket, "number": "HD-1", "responded_by": new_uuid(), "responded_at": at(20)},
    )
    assert deliver(desk.org.id, event.name, None, event=event) == "applied"
    before = len(outbox(STOPPED, desk.org.id)), desk.clocks(ticket)
    assert deliver(desk.org.id, event.name, None, event=event) == "duplicate"
    assert (len(outbox(STOPPED, desk.org.id)), desk.clocks(ticket)) == before
    created = FakeEvent(
        name="helpdesk.ticket.created",
        organisation_id=desk.org.id,
        payload={
            "ticket_id": ticket,
            "number": "HD-1",
            "category_id": CATEGORY,
            "queue_id": None,
            "priority": "high",
            "created_at": at(0),
        },
    )
    assert deliver(desk.org.id, created.name, None, event=created) == "ignored"  # same ticket, new event id
    assert len(outbox(STARTED, desk.org.id)) == 2


def test_another_organisations_ticket_ids_touch_nothing(desk, other_org):
    desk.policy()
    ticket = desk.ticket()
    payload = {"ticket_id": ticket, "number": "HD-1", "responded_by": new_uuid(), "responded_at": at(5)}
    assert deliver(other_org.id, "helpdesk.ticket.responded", payload) == "ignored"
    assert deliver(other_org.id, "helpdesk.ticket.cancelled", {"ticket_id": ticket, "cancelled_at": at(6)}) == "ignored"
    assert {c["state"] for c in desk.clocks(ticket).values()} == {"running"}
    assert outbox(STOPPED, other_org.id) == [] and outbox(STOPPED, desk.org.id) == []


def test_the_session_must_be_scoped_to_the_event_organisation(tables, org, other_org):
    from eos_core.db import SessionLocal
    from eos_core.tenant import organisation_scope

    event = FakeEvent(name=consumers.RESPONDED, organisation_id=org.id, payload={})
    with organisation_scope(other_org.id), SessionLocal() as db, pytest.raises(RuntimeError):
        CONSUMERS[consumers.RESPONDED](db, event)


CREATED_OK = {
    "ticket_id": "66666666-6666-4666-8666-666666666666",
    "number": "HD-7",
    "category_id": CATEGORY,
    "queue_id": None,
    "priority": "high",
    "created_at": "2026-11-02T09:00:00+00:00",
}


@pytest.mark.parametrize(
    "change",
    [
        {"ticket_id": 123},
        {"ticket_id": None},
        {"ticket_id": "not-a-uuid"},
        {"ticket_id": ["66666666-6666-4666-8666-666666666666"]},
        {"number": 7},
        {"number": "H" * 41},
        {"priority": "critical"},
        {"priority": None},
        {"category_id": 5},
        {"created_at": "yesterday"},
        {"created_at": 1700000000},
        {"created_at": "1900-01-01T00:00:00+00:00"},
        {"created_at": "9999-12-31T23:59:59+14:00"},
        {"created_at": "0001-01-01T00:00:00-12:00"},
        {"created_at": "2" * 10_000},
        {"created_at": None},
    ],
)
def test_malformed_payloads_are_ignored_without_raising(tables, org, change):
    payload = {**CREATED_OK, **change}
    assert deliver(org.id, consumers.CREATED, payload) == "ignored"
    assert outbox(STARTED, org.id) == []


@pytest.mark.parametrize("missing", sorted(CREATED_OK))
def test_a_missing_field_is_ignored(tables, org, missing):
    payload = {k: v for k, v in CREATED_OK.items() if k != missing}
    assert deliver(org.id, consumers.CREATED, payload) == "ignored"


@pytest.mark.parametrize(
    "envelope",
    [
        {"payload": "not an object"},
        {"payload": None},
        {"version": 2},
        {"id": 12345},
        {"id": "x" * 37},
        {"occurred_at": "garbage"},
    ],
)
def test_malformed_envelopes_are_ignored(tables, org, envelope):
    event = FakeEvent(
        **{
            "name": consumers.ASSIGNED,
            "organisation_id": org.id,
            "payload": {"ticket_id": CREATED_OK["ticket_id"], "queue_id": None, "assignee_id": None},
            **envelope,
        }
    )
    assert deliver(org.id, event.name, None, event=event) == "ignored"


def test_an_event_without_an_organisation_is_not_ours(tables):
    assert deliver(None, consumers.CREATED, CREATED_OK) == "ignored"
    assert deliver(None, consumers.CREATED, {**CREATED_OK, "organisation_id": new_uuid()}) == "ignored"


def test_every_handler_ignores_garbage(tables, org):
    for name in CONSUMERS:
        assert deliver(org.id, name, {"ticket_id": 1}) == "ignored", name
        assert deliver(org.id, name, {}) == "ignored", name
