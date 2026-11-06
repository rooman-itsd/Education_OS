"""The code's enums, keys and response shapes against the contract files themselves, so a contract change that the
code has not followed fails here instead of passing with hand-copied values."""

import inspect
import re
import typing
from pathlib import Path

import pytest
import yaml
from eos_sla_management.api import schemas
from eos_sla_management.application import engine, service
from eos_sla_management.application.access import PERMISSION_KEYS
from eos_sla_management.application.errors import STATUS_BY_KIND
from eos_sla_management.domain import clocks, policies

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


def properties(openapi, name) -> set[str]:
    """Every property of a schema, following allOf."""
    body = schema(openapi, name)
    found = set(body.get("properties", {}))
    for part in body.get("allOf", []):
        if "$ref" in part:
            found |= properties(openapi, part["$ref"].rsplit("/", 1)[1])
        found |= set(part.get("properties", {}))
    return found


def test_enums(openapi):
    assert list(policies.PRIORITIES) == schema(openapi, "Priority")["enum"]
    assert list(policies.HOLD_REASONS) == schema(openapi, "HoldReason")["enum"]
    assert list(clocks.KINDS) == schema(openapi, "ClockKind")["enum"]
    assert list(clocks.STATES) == schema(openapi, "ClockState")["enum"]
    assert list(clocks.OUTCOMES) == [v for v in schema(openapi, "Clock")["properties"]["outcome"]["enum"] if v]
    assert list(typing.get_args(schemas.Priority)) == list(policies.PRIORITIES)
    assert list(typing.get_args(schemas.HoldReason)) == list(policies.HOLD_REASONS)
    defaults = schema(openapi, "PolicyInput")["properties"]["pause_on_hold_reasons"]["default"]
    assert list(policies.DEFAULT_PAUSE_REASONS) == defaults
    assert schemas.PolicyInput.model_fields["pause_on_hold_reasons"].default_factory() == defaults
    scope = openapi["paths"]["/stats/breaches"]["get"]["parameters"][0]["schema"]["enum"]
    assert list(service.SCOPES) == scope


def test_input_schemas_have_the_contract_fields(openapi):
    for model, name in [
        (schemas.CalendarInput, "CalendarInput"),
        (schemas.CalendarUpdateInput, "CalendarInput"),
        (schemas.PolicyInput, "PolicyInput"),
        (schemas.PolicyUpdateInput, "PolicyInput"),
        (schemas.WorkingInterval, "WorkingInterval"),
        (schemas.Holiday, "Holiday"),
        (schemas.EscalationLevel, "EscalationLevel"),
    ]:
        assert set(model.model_fields) == set(schema(openapi, name)["properties"]), name
    for model, name in [(schemas.PolicyInput, "PolicyInput"), (schemas.CalendarInput, "CalendarInput")]:
        required = {n for n, f in model.model_fields.items() if f.is_required()}
        assert required == set(schema(openapi, name)["required"]), name


def test_serialised_shapes_have_every_contract_field(openapi):
    """The keys the service returns are exactly the contract's properties."""
    for fn, name in [
        (service.calendar_dict, "Calendar"),
        (service.policy_dict, "Policy"),
        (service.clock_dict, "Clock"),
    ]:
        keys = set(re.findall(r'^\s+"(\w+)":', inspect.getsource(fn), flags=re.M))
        assert keys == properties(openapi, name), name
    source = inspect.getsource(service.breach_stats) + inspect.getsource(service.get_clock)
    summary = schema(openapi, "BreachSummary")["properties"]
    for field in [*summary, *summary["most_overdue"]["items"]["properties"], *properties(openapi, "Escalation")]:
        assert f'"{field}"' in source, field


def test_permission_keys_are_the_catalogue(permissions):
    assert list(PERMISSION_KEYS) == [p["key"] for p in permissions["permissions"]]


def test_every_role_grants_only_catalogue_keys(permissions):
    for role in permissions["roles"]:
        assert set(role["grants"]) <= set(PERMISSION_KEYS), role["name"]


def test_published_event_names_are_the_catalogue(events):
    names = re.findall(r'publish\(\s*"([\w-]+)"', inspect.getsource(engine))
    assert {f"sla-management.clock.{n}" for n in names} == {e["name"] for e in events["events"]}


def test_mapped_statuses_are_ones_the_contract_answers(openapi):
    answered = {
        int(code)
        for path in openapi["paths"].values()
        for operation in path.values()
        for code in operation.get("responses", {})
    }
    assert set(STATUS_BY_KIND.values()) <= answered
