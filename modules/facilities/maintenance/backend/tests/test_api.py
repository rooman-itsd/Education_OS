"""Integration tests through the HTTP API, against a throwaway SQLite database (see conftest)."""

from datetime import timedelta

from conftest import BASE, NOW
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_maintenance.application import service
from eos_maintenance.application.jobs import run_sweeps
from eos_maintenance.infrastructure import repository as repo
from sqlalchemy import select, text

MANAGER = "maintenance-manager"
TECHNICIAN = "maintenance-technician"
REPORTER = "maintenance-reporter"

PROJECTOR = {"kind": "asset", "id": "AST-0142", "label": "AST-0142 · Projector, Lab 2"}


def events(org_id: str, name: str | None = None) -> list[OutboxEvent]:
    with SessionLocal() as db:
        q = select(OutboxEvent).where(OutboxEvent.organisation_id == org_id).order_by(text("rowid"))  # insertion order
        found = list(db.scalars(q))
    return [e for e in found if name is None or e.name == name]


def category(client, mgr, name="Electrical", **fields) -> dict:
    r = client.post(f"{BASE}/categories", json={"name": name} | fields, headers=mgr)
    assert r.status_code == 201, r.text
    return r.json()


def report(client, who, cat, *, target=PROJECTOR, **fields) -> dict:
    body = {"title": "Projector will not turn on", "category_id": cat["id"], "target": target} | fields
    r = client.post(f"{BASE}/tickets", json=body, headers=who)
    assert r.status_code == 201, r.text
    return r.json()


def act(client, who, ticket, action, body=None, expect=200) -> dict:
    r = client.post(f"{BASE}/tickets/{ticket['id']}/{action}", json=body, headers=who)
    assert r.status_code == expect, r.text
    return r.json()


def at(monkeypatch, moment):
    monkeypatch.setattr(service, "clock", lambda: moment)


# ---------------------------------------------------------------- categories


def test_categories_are_managed_by_managers_and_read_by_reporters(client, org):
    _, mgr = org.user(MANAGER)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr, default_priority="high", sla_override={"response_hours": {"high": 2}})
    assert cat["default_priority"] == "high"
    assert cat["organisation_id"] == org.id
    assert client.post(f"{BASE}/categories", json={"name": "Electrical"}, headers=mgr).status_code == 409
    assert client.post(f"{BASE}/categories", json={"name": "Plumbing"}, headers=rep).status_code == 403
    assert [c["name"] for c in client.get(f"{BASE}/categories", headers=rep).json()] == ["Electrical"]
    r = client.patch(f"{BASE}/categories/{cat['id']}", json={"active": False}, headers=mgr)
    assert r.json()["active"] is False
    blocked = client.post(
        f"{BASE}/tickets", json={"title": "x", "category_id": cat["id"], "target": PROJECTOR}, headers=rep
    )
    assert blocked.status_code == 422
    assert blocked.json()["detail"]["code"] == "unknown_category"


# ---------------------------------------------------------------- raising


def test_raise_applies_category_defaults_sla_and_number(client, org):
    _, mgr = org.user(MANAGER)
    tech_id, _ = org.user(TECHNICIAN)
    reporter_id, rep = org.user(REPORTER)
    cat = category(client, mgr, default_priority="high", default_assignee_ids=[tech_id])
    created = report(client, rep, cat, blocks_use=True)
    t = created["ticket"]
    assert created["possible_duplicates"] == []
    assert t["number"] == "MT-2026-00001"
    assert t["status"] == "assigned" and t["assignee_id"] == tech_id
    assert t["priority"] == "high"
    assert t["reported_by"] == reporter_id
    assert t["category_name"] == "Electrical"
    assert t["target"] == PROJECTOR
    assert t["response_due_at"] == (NOW + timedelta(hours=4)).isoformat()
    assert t["resolution_due_at"] == (NOW + timedelta(hours=48)).isoformat()
    assert t["sla_breached"] == []
    assert t["can"] == ["cancel"]  # the reporter may only cancel before work starts
    raised = events(org.id, "maintenance.ticket.raised")[0].payload
    assert raised["blocks_use"] is True and raised["target"] == PROJECTOR
    assert events(org.id, "maintenance.ticket.assigned")[0].payload["assignee_id"] == tech_id
    # same target and category again: warned, not refused
    again = report(client, rep, cat)
    assert again["possible_duplicates"] == [t["id"]]
    assert again["ticket"]["number"] == "MT-2026-00002"


def test_raise_rejects_bad_targets_and_two_assignees_leave_it_open(client, org):
    _, mgr = org.user(MANAGER)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr, default_assignee_ids=["u-1", "u-2"])
    bad = client.post(
        f"{BASE}/tickets",
        json={"title": "x", "category_id": cat["id"], "target": {"kind": "asset", "label": "No id"}},
        headers=rep,
    )
    assert bad.status_code == 422
    assert bad.json()["detail"]["code"] == "invalid_target"
    t = report(client, rep, cat, target={"kind": "location", "label": "Block B corridor"})["ticket"]
    assert t["status"] == "open" and t["assignee_id"] is None
    assert t["priority"] == "medium"


# ---------------------------------------------------------------- lifecycle


def test_full_lifecycle_with_hold_pausing_the_sla(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr)
    t = report(client, rep, cat)["ticket"]

    t = act(client, mgr, t, "assign", {"assignee_id": tech_id, "note": "Take the ladder"})
    assert t["status"] == "assigned" and t["assignee_id"] == tech_id

    at(monkeypatch, NOW + timedelta(hours=1))
    t = act(client, tech, t, "start")
    assert t["status"] == "in_progress"
    assert set(t["can"]) == {"hold", "resolve", "log_work"}

    at(monkeypatch, NOW + timedelta(hours=2))
    t = act(client, tech, t, "hold", {"reason": "waiting_parts", "note": "Lamp ordered"})
    assert t["status"] == "on_hold" and t["hold_reason"] == "waiting_parts"
    assert act(client, tech, t, "resolve", {"note": "x"}, expect=409)["detail"]["code"] == "not_in_progress"

    at(monkeypatch, NOW + timedelta(hours=5))
    resumed = act(client, tech, t, "start")
    assert resumed["status"] == "in_progress" and resumed["hold_reason"] is None
    # three hours on hold moved the resolution target out by three hours
    assert resumed["resolution_due_at"] == (NOW + timedelta(hours=120 + 3)).isoformat()

    assert act(client, tech, t, "resolve", {"note": " "}, expect=422)
    at(monkeypatch, NOW + timedelta(hours=6))
    done = act(client, tech, t, "resolve", {"note": "Replaced the lamp", "root_cause": "Lamp end of life"})
    assert done["status"] == "resolved"
    assert "close" not in done["can"]  # the technician is not the reporter
    closed = act(client, rep, t, "close", {"rating": 5, "feedback": "Quick, thanks"})
    assert closed["status"] == "closed"

    names = [e.name for e in events(org.id)]
    for name in ("raised", "assigned", "started", "put-on-hold", "resolved", "closed"):
        assert f"maintenance.ticket.{name}" in names
    closed_event = events(org.id, "maintenance.ticket.closed")[0].payload
    assert closed_event == {"organisation_id": org.id, "ticket_id": t["id"], "closed_by": "reporter", "rating": 5}

    detail = client.get(f"{BASE}/tickets/{t['id']}", headers=rep).json()
    assert detail["resolution"]["note"] == "Replaced the lamp"
    assert [e["note"] for e in detail["work_entries"]] == ["Assigned: Take the ladder", "On hold: Lamp ordered"]


def test_only_the_assignee_or_a_manager_works_on_a_ticket(client, org):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, other_tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr, default_assignee_ids=[tech_id])
    t = report(client, rep, cat)["ticket"]
    # the other technician cannot even see it
    assert client.post(f"{BASE}/tickets/{t['id']}/start", headers=other_tech).status_code == 404
    assert client.post(f"{BASE}/tickets/{t['id']}/start", headers=rep).status_code == 403
    assert (
        client.post(f"{BASE}/tickets/{t['id']}/assign", json={"assignee_id": tech_id}, headers=tech).status_code == 403
    )
    # a vendor job is run by the manager
    vendor = act(client, mgr, t, "assign", {"vendor": {"name": "Brightline Electricals", "job_number": "J-77"}})
    assert vendor["vendor"]["name"] == "Brightline Electricals" and vendor["assignee_id"] is None
    assert events(org.id, "maintenance.ticket.assigned")[-1].payload["previous_assignee_id"] == tech_id
    assert act(client, mgr, t, "start")["status"] == "in_progress"
    both = client.post(
        f"{BASE}/tickets/{t['id']}/assign", json={"assignee_id": tech_id, "vendor": {"name": "V"}}, headers=mgr
    )
    assert both.status_code == 422


def test_scopes_and_visibility(client, org):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    _, rep2 = org.user(REPORTER)
    cat = category(client, mgr, default_assignee_ids=[tech_id])
    t = report(client, rep, cat)["ticket"]
    assert [x["id"] for x in client.get(f"{BASE}/tickets", headers=rep).json()["items"]] == [t["id"]]
    assert client.get(f"{BASE}/tickets", headers=rep2).json()["items"] == []
    assert client.get(f"{BASE}/tickets/{t['id']}", headers=rep2).status_code == 404
    assert client.get(f"{BASE}/tickets?scope=assigned", headers=tech).json()["total"] == 1
    assert client.get(f"{BASE}/tickets?scope=managed", headers=tech).status_code == 403
    managed = client.get(f"{BASE}/tickets?scope=managed&open=true&priority=medium,high", headers=mgr).json()
    assert managed["total"] == 1
    assert client.get(f"{BASE}/tickets?scope=managed&q=projector", headers=mgr).json()["total"] == 1
    assert client.get(f"{BASE}/tickets?scope=managed&status=bogus", headers=mgr).status_code == 422


def test_reopen_within_the_window_goes_back_to_the_assignee(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr, default_assignee_ids=[tech_id])
    t = report(client, rep, cat)["ticket"]
    act(client, tech, t, "start")
    act(client, tech, t, "resolve", {"note": "Tightened the cable"})
    act(client, rep, t, "close")
    at(monkeypatch, NOW + timedelta(days=6))
    again = act(client, rep, t, "reopen", {"reason": "Flickering again"})
    assert again["status"] == "assigned" and again["resolved_at"] is None
    assert events(org.id, "maintenance.ticket.reopened")[0].payload["reason"] == "Flickering again"
    act(client, tech, t, "start")
    act(client, tech, t, "resolve", {"note": "Replaced the cable"})
    at(monkeypatch, NOW + timedelta(days=14))
    late = act(client, rep, t, "reopen", {"reason": "Again"}, expect=409)
    assert late["detail"]["code"] == "reopen_window_passed"


def test_cancel_rules(client, org):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr, default_assignee_ids=[tech_id])
    first = report(client, rep, cat)["ticket"]
    second = report(client, rep, cat)["ticket"]
    gone = act(client, rep, second, "cancel", {"reason": "Same fault", "duplicate_of": first["id"]})
    assert gone["status"] == "cancelled"
    assert events(org.id, "maintenance.ticket.cancelled")[0].payload["duplicate_of"] == first["id"]
    act(client, tech, first, "start")
    assert act(client, rep, first, "cancel", {"reason": "Fixed itself"}, expect=409)
    assert act(client, mgr, first, "cancel", {"reason": "Room closed"})["status"] == "cancelled"
    assert client.patch(f"{BASE}/tickets/{first['id']}", json={"title": "x"}, headers=mgr).status_code == 409


def test_priority_change_recomputes_the_sla(client, org):
    _, mgr = org.user(MANAGER)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr)
    t = report(client, rep, cat)["ticket"]
    assert client.patch(f"{BASE}/tickets/{t['id']}", json={"priority": "urgent"}, headers=rep).status_code == 403
    r = client.patch(f"{BASE}/tickets/{t['id']}", json={"priority": "urgent", "blocks_use": True}, headers=mgr).json()
    assert r["priority"] == "urgent" and r["blocks_use"] is True
    assert r["response_due_at"] == (NOW + timedelta(hours=1)).isoformat()
    assert r["resolution_due_at"] == (NOW + timedelta(hours=8)).isoformat()
    changed = events(org.id, "maintenance.ticket.priority-changed")[0].payload
    assert (changed["from"], changed["to"]) == ("medium", "urgent")


def test_patch_refuses_explicit_null_on_fields_that_cannot_be_empty(client, org):
    _, mgr = org.user(MANAGER)
    cat = category(client, mgr)
    t = report(client, mgr, cat)["ticket"]
    for body in ({"title": None}, {"priority": None}, {"blocks_use": None}):
        r = client.patch(f"{BASE}/tickets/{t['id']}", json=body, headers=mgr)
        assert r.status_code == 422, (body, r.text)
    cleared = client.patch(f"{BASE}/tickets/{t['id']}", json={"description": None}, headers=mgr)
    assert cleared.status_code == 200 and cleared.json()["description"] is None  # description may be emptied
    assert client.patch(f"{BASE}/categories/{cat['id']}", json={"name": None}, headers=mgr).status_code == 422
    s = client.post(f"{BASE}/schedules", json=schedule_body(cat), headers=mgr).json()
    assert client.patch(f"{BASE}/schedules/{s['id']}", json={"next_due_on": None}, headers=mgr).status_code == 422
    assert client.patch(f"{BASE}/schedules/{s['id']}", json={"every": None}, headers=mgr).status_code == 422
    reset = client.patch(f"{BASE}/schedules/{s['id']}", json={"lead_days": None}, headers=mgr)
    assert reset.status_code == 200 and reset.json()["lead_days"] == 3  # null lead_days means the default again


def test_raise_retries_once_when_two_raises_get_the_same_number(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    cat = category(client, mgr)
    first = report(client, mgr, cat)["ticket"]
    real, calls = repo.next_number, []

    def colliding(db, organisation_id, year):
        calls.append(1)
        return first["number"] if len(calls) == 1 else real(db, organisation_id, year)

    monkeypatch.setattr(repo, "next_number", colliding)
    second = report(client, mgr, cat)["ticket"]  # the first attempt hits uq_maintenance_ticket_number, the retry wins
    assert len(calls) == 2
    assert second["number"] == "MT-2026-00002" and second["id"] != first["id"]
    ids = {x["id"] for x in client.get(f"{BASE}/tickets?scope=managed", headers=mgr).json()["items"]}
    assert ids == {first["id"], second["id"]}


# ---------------------------------------------------------------- work log


def test_work_log_permissions_and_totals(client, org):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr, default_assignee_ids=[tech_id])
    t = report(client, rep, cat)["ticket"]
    url = f"{BASE}/tickets/{t['id']}/work-entries"
    assert client.post(url, json={"kind": "note", "note": "It smells of burning"}, headers=rep).status_code == 201
    assert client.post(url, json={"kind": "time", "minutes": 30}, headers=rep).status_code == 403
    assert client.post(url, json={"kind": "time", "minutes": 45}, headers=tech).status_code == 201
    part = {"kind": "part", "item_name": "Lamp 230V", "quantity": 1, "cost": {"amount": "1200.50", "currency": "INR"}}
    assert client.post(url, json=part, headers=tech).status_code == 201
    other = client.post(url, json={"kind": "cost", "cost": {"amount": "10", "currency": "USD"}}, headers=tech)
    assert other.status_code == 422 and other.json()["detail"]["code"] == "currency_mismatch"
    assert (
        client.post(url, json={"kind": "cost", "cost": {"amount": "99.5", "currency": "INR"}}, headers=tech).status_code
        == 201
    )
    entries = client.get(url, headers=rep).json()
    assert [e["kind"] for e in entries] == ["note", "time", "part", "cost"]
    got = client.get(f"{BASE}/tickets/{t['id']}", headers=mgr).json()
    assert got["total_minutes"] == 45
    assert got["total_cost"] == {"amount": "1300.00", "currency": "INR"}


# ---------------------------------------------------------------- SLA sweep and widget


def test_sweep_flags_breaches_once_and_widget_counts(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr)
    urgent = report(client, rep, cat, priority="urgent")["ticket"]
    calm = report(client, rep, cat, priority="low", target={"kind": "location", "label": "Canteen tap"})["ticket"]
    act(client, mgr, calm, "assign", {"assignee_id": tech_id})
    later = NOW + timedelta(hours=2)
    at(monkeypatch, later)
    with SessionLocal() as db:
        assert run_sweeps(db, now=later)["sla_breached"] >= 1
    with SessionLocal() as db:
        run_sweeps(db, now=later)  # a second sweep publishes nothing new
    breached = [e.payload for e in events(org.id, "maintenance.ticket.sla-breached")]
    assert [(b["ticket_id"], b["which"]) for b in breached] == [(urgent["id"], "response")]

    listed = client.get(f"{BASE}/tickets?scope=managed&open=true", headers=mgr).json()["items"]
    assert [x["id"] for x in listed] == [urgent["id"], calm["id"]]  # breached first
    assert listed[0]["sla_breached"] == ["response"]
    assert client.get(f"{BASE}/tickets?scope=managed&sla_breached=true", headers=mgr).json()["total"] == 1

    summary = client.get(f"{BASE}/summary", headers=mgr).json()
    assert summary == {
        "open": 2,
        "unassigned": 1,
        "in_progress": 0,
        "on_hold": 0,
        "urgent_open": 1,
        "sla_breached_open": 1,
        "resolved_awaiting_confirmation": 0,
        "preventive_due_7_days": 0,
    }
    mine = client.get(f"{BASE}/summary", headers=tech).json()
    assert mine["open"] == 1 and mine["urgent_open"] == 0


def test_sweep_auto_closes_resolved_tickets(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr, default_assignee_ids=[tech_id])
    t = report(client, rep, cat)["ticket"]
    act(client, tech, t, "start")
    act(client, tech, t, "resolve", {"note": "Done"})
    later = NOW + timedelta(days=3)
    at(monkeypatch, later)
    with SessionLocal() as db:
        assert run_sweeps(db, now=later)["auto_closed"] >= 1
    assert client.get(f"{BASE}/tickets/{t['id']}", headers=rep).json()["status"] == "closed"
    assert events(org.id, "maintenance.ticket.closed")[0].payload["closed_by"] == "auto"


# ---------------------------------------------------------------- preventive schedules


def schedule_body(cat, **fields) -> dict:
    return {
        "title": "Service the air conditioner",
        "category_id": cat["id"],
        "target": {"kind": "resource", "id": "RES-7", "label": "Seminar hall"},
        "every": 3,
        "unit": "months",
        "next_due_on": "2026-10-14",
        "checklist": ["Clean filters", "Check gas"],
    } | fields


def test_schedule_raises_preventive_tickets_without_drift(client, org, monkeypatch):
    _, mgr = org.user(MANAGER)
    tech_id, tech = org.user(TECHNICIAN)
    _, rep = org.user(REPORTER)
    cat = category(client, mgr)
    assert client.post(f"{BASE}/schedules", json=schedule_body(cat), headers=rep).status_code == 403
    s = client.post(f"{BASE}/schedules", json=schedule_body(cat, default_assignee_id=tech_id), headers=mgr)
    assert s.status_code == 201, s.text
    s = s.json()
    assert s["lead_days"] == 3  # MAINTENANCE_DEFAULT_LEAD_DAYS
    assert events(org.id, "maintenance.schedule.created")[0].payload["next_due_on"] == "2026-10-14"
    assert client.get(f"{BASE}/summary", headers=mgr).json()["preventive_due_7_days"] == 1

    with SessionLocal() as db:
        assert run_sweeps(db, now=NOW)["preventive_raised"] == 1  # due 14 Oct, 3 days lead, today 12 Oct
    with SessionLocal() as db:
        assert run_sweeps(db, now=NOW)["preventive_raised"] == 0  # never two open tickets
    s = client.get(f"{BASE}/schedules/{s['id']}", headers=mgr).json()
    assert s["next_due_on"] == "2027-01-14"  # moved from the scheduled date
    assert len(s["recent_tickets"]) == 1
    ticket = client.get(f"{BASE}/tickets/{s['open_ticket_id']}", headers=mgr).json()
    assert ticket["kind"] == "preventive" and ticket["status"] == "assigned" and ticket["assignee_id"] == tech_id
    assert ticket["checklist"] == [{"step": "Clean filters", "done": False}, {"step": "Check gas", "done": False}]
    assert ticket["reported_by"] == "scheduler"
    assert client.post(f"{BASE}/schedules/{s['id']}/raise-now", headers=mgr).status_code == 409

    act(client, tech, ticket, "start")
    act(
        client,
        tech,
        ticket,
        "resolve",
        {
            "note": "Serviced",
            "checklist": [{"step": "Clean filters", "done": True}, {"step": "Check gas", "done": True}],
        },
    )
    s = client.get(f"{BASE}/schedules/{s['id']}", headers=mgr).json()
    assert s["open_ticket_id"] is None and s["last_completed_on"] == "2026-10-12"
    early = client.post(f"{BASE}/schedules/{s['id']}/raise-now", headers=mgr)
    assert early.status_code == 201 and early.json()["kind"] == "preventive"
    assert client.get(f"{BASE}/schedules/{s['id']}", headers=mgr).json()["next_due_on"] == "2027-04-14"


def test_schedule_pause_and_delete(client, org):
    _, mgr = org.user(MANAGER)
    cat = category(client, mgr)
    s = client.post(f"{BASE}/schedules", json=schedule_body(cat, lead_days=0), headers=mgr).json()
    paused = client.patch(f"{BASE}/schedules/{s['id']}", json={"active": False}, headers=mgr).json()
    assert paused["active"] is False
    assert client.get(f"{BASE}/schedules?active=true", headers=mgr).json() == []
    with SessionLocal() as db:
        assert run_sweeps(db, now=NOW + timedelta(days=5))["preventive_raised"] == 0
    assert client.delete(f"{BASE}/schedules/{s['id']}", headers=mgr).status_code == 204
    assert client.get(f"{BASE}/schedules/{s['id']}", headers=mgr).status_code == 404
    gone = [e.payload["deleted"] for e in events(org.id, "maintenance.schedule.deactivated")]
    assert gone == [False, True]
