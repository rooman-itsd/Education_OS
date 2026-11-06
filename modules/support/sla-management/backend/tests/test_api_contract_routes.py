"""Every operation in contracts/openapi.yaml has a route, and every route is in the contract; every event the module
publishes carries exactly the fields events.yaml lists."""

from datetime import timedelta
from pathlib import Path

import yaml
from conftest import NOW, at, outbox

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
METHODS = {"get", "post", "patch", "put", "delete"}


def test_routes_match_the_contract_operations():
    from eos_sla_management.api.router import router

    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract = {(m.upper(), path) for path, item in spec["paths"].items() for m in item if m in METHODS}
    routes = set()
    for route in router.routes:
        path = route.path
        for name in ("{calendar_id}", "{policy_id}", "{clock_id}"):
            path = path.replace(name, "{id}")
        routes |= {(m, path) for m in route.methods}
    assert routes == contract
    assert len(contract) == 12


def test_event_payloads_match_events_yaml(desk):
    """Every published payload carries exactly the fields events.yaml lists."""
    spec = yaml.safe_load((CONTRACT.parent / "events.yaml").read_text(encoding="utf-8"))
    cal = desk.calendar()["id"]
    desk.policy(cal)
    desk.policy(cal, priority="urgent", response_target_minutes=30, resolution_target_minutes=120)
    ticket = desk.ticket()
    desk.assign(ticket, desk.agent_id)
    hold = {"ticket_id": ticket, "to_status": "on_hold", "hold_reason": "waiting_requester", "changed_at": at(10)}
    desk.send("status-changed", hold)
    desk.send("status-changed", {**hold, "to_status": "in_progress", "hold_reason": None, "changed_at": at(20)})
    reclassified = {"ticket_id": ticket, "category_id": None, "priority": "urgent"}
    desk.send("reclassified", reclassified, occurred_at=NOW + timedelta(minutes=25))
    desk.send("responded", {"ticket_id": ticket, "responded_at": at(200)})  # late: warning, breach, escalations
    other = desk.ticket()
    desk.send("cancelled", {"ticket_id": other, "cancelled_at": at(5)})
    for event in spec["events"]:
        payloads = outbox(event["name"], desk.org.id)
        assert payloads, event["name"]
        for payload in payloads:
            assert set(payload) == set(event["payload"]), event["name"]
