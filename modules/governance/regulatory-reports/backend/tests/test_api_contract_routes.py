"""Every operation in contracts/openapi.yaml has a route, and every route is in the contract; every published event
payload carries exactly the fields events.yaml lists."""

from pathlib import Path

import yaml

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
METHODS = {"get", "post", "patch", "put", "delete"}


def test_routes_match_the_contract_operations():
    from eos_regulatory_reports.api.router import router

    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract = {(m.upper(), path) for path, item in spec["paths"].items() for m in item if m in METHODS}
    routes = set()
    for route in router.routes:
        path = route.path.replace("{obligation_id}", "{id}").replace("{filing_id}", "{id}")
        routes |= {(m, path) for m in route.methods}
    assert routes == contract
    assert len(contract) == 13


def test_events_payloads_match_events_yaml(client, org, clock):
    from conftest import Desk, days, outbox

    spec = yaml.safe_load((CONTRACT.parent / "events.yaml").read_text(encoding="utf-8"))
    d = Desk(client, org)
    f = d.filing()
    d.move(f["id"], "in_preparation", d.preparer)
    d.move(f["id"], "under_review", d.preparer)
    d.ok(d.post(f"/filings/{f['id']}/submit", {"submitted_on": days(0), "submission_reference": "R-1"}))
    d.ok(d.post(f"/filings/{f['id']}/acknowledge", {"acknowledged_on": days(0)}))
    for event in spec["events"]:
        payloads = outbox(event["name"], org.id)
        assert payloads, event["name"]
        assert set(payloads[-1]) == set(event["payload"]), event["name"]
