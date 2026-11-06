"""Every operation in contracts/openapi.yaml has a route, and every route is in the contract."""

from pathlib import Path

import yaml

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
METHODS = {"get", "post", "patch", "put", "delete"}


def test_routes_match_the_contract_operations():
    from eos_incident_management.api.router import router

    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract = {(m.upper(), path) for path, item in spec["paths"].items() for m in item if m in METHODS}
    routes = set()
    for route in router.routes:
        path = route.path.replace("{incident_id}", "{id}").replace("{problem_id}", "{id}")
        routes |= {(m, path) for m in route.methods}
    assert routes == contract
    assert len(contract) == 20


def test_events_payloads_match_events_yaml(client, org, clock):
    """Every published payload carries exactly the fields events.yaml lists."""
    from conftest import Desk, outbox

    spec = yaml.safe_load((CONTRACT.parent / "events.yaml").read_text(encoding="utf-8"))
    d = Desk(client, org)
    incident = d.incident()
    d.ok(d.patch(f"/incidents/{incident['id']}", {"severity": "critical"}, d.responder))
    d.move(incident["id"], "investigating")
    problem = d.problem()
    d.ok(d.post(f"/problems/{problem['id']}/status", {"status": "investigating"}))
    d.published(problem["id"])
    d.action(problem["id"])
    for event in spec["events"]:
        payloads = outbox(event["name"], org.id)
        assert payloads, event["name"]
        assert set(payloads[-1]) == set(event["payload"]), event["name"]
