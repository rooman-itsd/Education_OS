"""Every operation in contracts/openapi.yaml has a route, and every route is in the contract."""

from pathlib import Path

import yaml

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
METHODS = {"get", "post", "patch", "put", "delete"}


def test_routes_match_the_contract_operations():
    from eos_amc_vendor_support.api.router import router

    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract = {(m.upper(), path) for path, item in spec["paths"].items() for m in item if m in METHODS}
    routes = set()
    for route in router.routes:
        path = route.path.replace("{contract_id}", "{id}").replace("{engagement_id}", "{id}")
        routes |= {(m, path) for m in route.methods}
    assert routes == contract
    assert len(contract) == 16


def test_events_payloads_match_events_yaml(client, org, clock):
    """Every published payload carries exactly the fields events.yaml lists."""
    from conftest import Desk, days, outbox

    spec = yaml.safe_load((CONTRACT.parent / "events.yaml").read_text(encoding="utf-8"))
    d = Desk(client, org)
    original = d.active()
    successor = d.ok(d.post(f"/contracts/{original['id']}/renew", {"end_date": days(900)}))
    d.ok(d.post(f"/contracts/{successor['id']}/activate", {}))
    other = d.active()
    d.ok(d.post(f"/contracts/{other['id']}/terminate", {"reason": "Ended", "effective_date": days(0)}))
    for event in spec["events"]:
        payloads = outbox(event["name"], org.id)
        assert payloads, event["name"]
        assert set(payloads[-1]) == set(event["payload"]), event["name"]
