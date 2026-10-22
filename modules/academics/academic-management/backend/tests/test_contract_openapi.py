"""Contract checks on contracts/openapi.yaml: every operation names the permission it requires (x-permission, as
info.description states) and declares the 403 a caller without that permission receives."""

from pathlib import Path

import pytest
import yaml

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
METHODS = {"get", "put", "post", "patch", "delete", "options", "head", "trace"}
OPERATIONS = [
    (f"{method.upper()} {path}", op)
    for path, item in CONTRACT["paths"].items()
    for method, op in item.items()
    if method in METHODS
]


def test_the_contract_has_operations():
    assert len(OPERATIONS) >= 34


@pytest.mark.parametrize(("name", "op"), OPERATIONS, ids=[name for name, _ in OPERATIONS])
def test_every_operation_names_its_permission(name, op):
    assert str(op.get("x-permission", "")).startswith("academic-management:"), name


@pytest.mark.parametrize(("name", "op"), OPERATIONS, ids=[name for name, _ in OPERATIONS])
def test_every_permission_checked_operation_declares_the_shared_403(name, op):
    assert op["responses"].get("403") == {"$ref": "#/components/responses/Forbidden"}, name


def test_the_shared_403_returns_the_contract_error_response():
    forbidden = CONTRACT["components"]["responses"]["Forbidden"]
    assert forbidden["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ErrorResponse"}
    assert set(CONTRACT["components"]["schemas"]["ErrorResponse"]["required"]) == {"code", "message"}
