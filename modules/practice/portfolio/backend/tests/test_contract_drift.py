"""Verify that all paths declared in contracts/openapi.yaml exist on the router."""

from pathlib import Path
import yaml
from eos_portfolio.api.router import router

CONTRACT = Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml"


def test_contract_paths_implemented():
    spec = yaml.safe_load(CONTRACT.read_text(encoding="utf-8"))
    contract_paths = set(spec.get("paths", {}).keys())

    router_paths = set()
    for route in router.routes:
        path = getattr(route, "path", None)
        if path:
            router_paths.add(path)

    missing = contract_paths - router_paths
    assert not missing, f"Router is missing routes defined in openapi.yaml: {missing}"

