"""Every operation in contracts/openapi.yaml has a route, and every route is in the contract."""

from pathlib import Path

import yaml

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"
METHODS = {"get", "post", "patch", "put", "delete"}


def test_routes_match_the_contract_operations():
    from eos_helpdesk.api.router import router

    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract = {(m.upper(), path) for path, item in spec["paths"].items() for m in item if m in METHODS}
    routes = set()
    for route in router.routes:
        path = route.path.replace("{ticket_id}", "{id}").replace("{queue_id}", "{id}").replace("{category_id}", "{id}")
        routes |= {(m, path) for m in route.methods}
    assert routes == contract
    assert len(contract) == 25
