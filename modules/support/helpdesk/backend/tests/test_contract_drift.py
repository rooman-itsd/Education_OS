"""The code's enums, keys and response shapes against the contract files themselves, so a contract change that the
code has not followed fails here instead of passing with hand-copied values."""

import dataclasses
from pathlib import Path

import pytest
import yaml
from eos_helpdesk.application.access import PERMISSION_KEYS
from eos_helpdesk.application.errors import STATUS_BY_KIND
from eos_helpdesk.domain import stats, tickets

CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"


@pytest.fixture(scope="module")
def openapi():
    return yaml.safe_load((CONTRACTS / "openapi.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def permissions():
    return yaml.safe_load((CONTRACTS / "permissions.yaml").read_text(encoding="utf-8"))


def schema(openapi, name):
    return openapi["components"]["schemas"][name]


def test_ticket_status_priority_and_hold_reason_enums(openapi):
    assert list(tickets.TICKET_STATUSES) == schema(openapi, "TicketStatus")["enum"]
    assert list(tickets.PRIORITIES) == schema(openapi, "Priority")["enum"]
    assert list(tickets.HOLD_REASONS) == schema(openapi, "HoldReason")["enum"]


def test_status_input_offers_exactly_start_and_hold(openapi):
    assert schema(openapi, "StatusInput")["properties"]["status"]["enum"] == [tickets.IN_PROGRESS, tickets.ON_HOLD]


def test_open_by_priority_scope_and_default(openapi):
    assert list(stats.SCOPES) == schema(openapi, "OpenByPriority")["properties"]["scope"]["enum"]
    params = openapi["paths"]["/stats/open-by-priority"]["get"]["parameters"]
    scope = next(p for p in params if p.get("name") == "scope")
    assert scope["schema"]["enum"] == list(stats.SCOPES)
    assert scope["schema"]["default"] == stats.DEFAULT_SCOPE


def test_open_by_priority_fields(openapi):
    body = schema(openapi, "OpenByPriority")
    assert [f.name for f in dataclasses.fields(stats.OpenByPriority)] == list(body["properties"])
    row = body["properties"]["rows"]["items"]
    fields = [f.name for f in dataclasses.fields(stats.PriorityRow)]
    assert fields == list(row["properties"])
    assert set(row["required"]) <= set(fields)


def test_counted_ticket_fields_exist_on_ticket(openapi):
    ticket = schema(openapi, "Ticket")["properties"]
    assert all(f.name in ticket for f in dataclasses.fields(stats.CountedTicket))


def test_permission_keys_are_the_catalogue(permissions):
    assert list(PERMISSION_KEYS) == [p["key"] for p in permissions["permissions"]]


def test_every_role_grants_only_catalogue_keys(permissions):
    for role in permissions["roles"]:
        assert set(role["grants"]) <= set(PERMISSION_KEYS), role["name"]


def test_mapped_statuses_are_ones_the_contract_answers(openapi):
    answered = {
        int(code)
        for path in openapi["paths"].values()
        for operation in path.values()
        for code in operation.get("responses", {})
    }
    assert set(STATUS_BY_KIND.values()) <= answered
    assert 403 in answered
