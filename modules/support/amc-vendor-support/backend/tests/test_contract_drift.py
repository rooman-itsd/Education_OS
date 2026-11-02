"""The code's enums, keys and response shapes against the contract files themselves, so a contract change that the
code has not followed fails here instead of passing with hand-copied values."""

import dataclasses
from pathlib import Path

import pytest
import yaml
from eos_amc_vendor_support.application.access import PERMISSION_KEYS
from eos_amc_vendor_support.application.errors import STATUS_BY_KIND
from eos_amc_vendor_support.domain import contracts, engagements, expiring

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


@pytest.fixture(scope="module")
def openapi():
    return yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def permissions():
    return yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def events():
    return yaml.safe_load((CONTRACTS / "events.yaml").read_text(encoding="utf-8"))


def schema(openapi, name):
    return openapi["components"]["schemas"][name]


def test_enums(openapi):
    assert list(contracts.CONTRACT_STATUSES) == schema(openapi, "ContractStatus")["enum"]
    assert list(contracts.COVERAGE_TYPES) == schema(openapi, "CoverageType")["enum"]
    assert list(engagements.ENGAGEMENT_STATUSES) == schema(openapi, "EngagementStatus")["enum"]
    assert list(engagements.ENGAGEMENT_KINDS) == schema(openapi, "EngagementKind")["enum"]
    status_input = schema(openapi, "EngagementStatusInput")["properties"]["status"]["enum"]
    assert list(engagements.TARGET_STATUSES) == status_input


def test_active_editable_fields_are_contract_fields(openapi):
    fields = set(schema(openapi, "ContractUpdateInput")["properties"])
    assert contracts.ACTIVE_EDITABLE_FIELDS <= fields
    assert contracts.ACTIVE_EDITABLE_FIELDS == {"owner_id", "vendor_contacts", "renewal_notice_days"}


def test_expiring_fields(openapi):
    body = schema(openapi, "ExpiringContracts")
    assert [f.name for f in dataclasses.fields(expiring.ExpiringContracts)] == list(body["properties"])
    item = body["properties"]["items"]["items"]
    fields = [f.name for f in dataclasses.fields(expiring.ExpiringItem)]
    assert fields == list(item["properties"])
    assert set(item["required"]) <= set(fields)


def test_serialised_contract_and_engagement_have_every_contract_field(openapi):
    """The keys service.contract_dict and engagement_dict return are exactly the contract's properties."""
    import inspect

    from eos_amc_vendor_support.application import service

    source = inspect.getsource(service.contract_dict) + inspect.getsource(service.engagement_dict)
    for name in ("Contract", "Engagement"):
        for field in schema(openapi, name)["properties"]:
            assert f'"{field}"' in source, (name, field)


def test_permission_keys_are_the_catalogue(permissions):
    assert list(PERMISSION_KEYS) == [p["key"] for p in permissions["permissions"]]


def test_every_role_grants_only_catalogue_keys(permissions):
    for role in permissions["roles"]:
        assert set(role["grants"]) <= set(PERMISSION_KEYS), role["name"]


def test_published_event_names_are_the_catalogue(events):
    assert {e["name"] for e in events["events"]} == {
        "amc-vendor-support.contract.activated",
        "amc-vendor-support.contract.renewed",
        "amc-vendor-support.contract.terminated",
    }


def test_mapped_statuses_are_ones_the_contract_answers(openapi):
    answered = {
        int(code)
        for path in openapi["paths"].values()
        for operation in path.values()
        for code in operation.get("responses", {})
    }
    assert set(STATUS_BY_KIND.values()) <= answered
