"""Unit tests of the error mapping (application layer): each domain error kind becomes the response the contract
declares for it, with the contract's ErrorResponse body."""

from pathlib import Path

import pytest
import yaml
from eos_academic_management.application.errors import STATUS_BY_KIND, AcademicManagementError, from_domain, not_found
from eos_academic_management.domain.errors import DomainRuleError

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)


@pytest.mark.parametrize(
    ("kind", "status"), [("invalid", 400), ("not_found", 404), ("conflict", 409), ("unprocessable", 422)]
)
def test_domain_kinds_map_to_contract_statuses(kind, status):
    err = from_domain(DomainRuleError("some_rule", "a message", kind=kind))
    assert (err.status, err.code, err.message) == (status, "some_rule", "a message")


def test_the_offending_field_goes_in_details():
    err = from_domain(DomainRuleError("below_minimum", "capacity must be at least 1", kind="invalid", field="capacity"))
    assert err.body() == {
        "code": "below_minimum",
        "message": "capacity must be at least 1",
        "details": {"field": "capacity"},
    }


def test_body_has_only_code_and_message_without_details():
    assert from_domain(DomainRuleError("term_dates_overlap", "overlaps T1", kind="conflict")).body() == {
        "code": "term_dates_overlap",
        "message": "overlaps T1",
    }


def test_not_found_carries_its_code():
    err = not_found("active_term_not_found", "no term is active")
    assert isinstance(err, AcademicManagementError)
    assert (err.status, err.body()) == (404, {"code": "active_term_not_found", "message": "no term is active"})


# --- contract drift


def test_every_mapped_status_is_a_response_the_contract_defines():
    statuses = {"BadRequest": 400, "NotFound": 404, "Conflict": 409, "Unprocessable": 422}
    responses = CONTRACT["components"]["responses"]
    assert set(statuses) <= set(responses)
    assert set(STATUS_BY_KIND.values()) == set(statuses.values())


@pytest.mark.parametrize("field", [None, "items[0].credits"])
def test_error_bodies_match_the_contract_error_response(field):
    schema = CONTRACT["components"]["schemas"]["ErrorResponse"]
    body = from_domain(DomainRuleError("credits_mismatch", "does not add up", kind="unprocessable", field=field)).body()
    assert set(schema["required"]) <= set(body) <= set(schema["properties"])
    assert all(isinstance(body[key], str) for key in ("code", "message"))
    assert "details" not in body or isinstance(body["details"], dict)
