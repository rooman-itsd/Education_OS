"""Tests of the faculty-load response schema: it accepts what the use case returns, mirrors the contract's
FacultyLoadReport and FacultyLoad, and rejects data the contract does not allow."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from eos_academic_management.api.schemas import FacultyLoadOut, FacultyLoadReportOut
from eos_academic_management.application.access import FACULTY_LOAD_READ, Actor
from eos_academic_management.application.faculty_load import faculty_load_report
from eos_academic_management.domain.load import LoadEntry
from eos_academic_management.domain.terms import ACTIVE, DateRange, Term
from pydantic import ValidationError

SCHEMAS = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)["components"]["schemas"]

PERIOD = "3f1c2a8e-5b7d-4c1e-9a2b-6d4e8f0a1b2c"
DEPT = "9a8b7c6d-5e4f-4a3b-8c2d-1e0f9a8b7c6d"
F1 = "11111111-1111-4111-8111-111111111111"
F2 = "22222222-2222-4222-8222-222222222222"
TERM = Term(PERIOD, "2026-ODD", "Odd Semester 2026", DateRange(date(2026, 7, 1), date(2026, 11, 30)), ACTIVE)


def use_case_output(**kwargs) -> dict:
    values = {
        "period": TERM,
        "entries": [
            LoadEntry(F1, "o1", "primary", Decimal(12), "active"),
            LoadEntry(F1, "o2", "co_instructor", Decimal("7.5"), "active"),
            LoadEntry(F2, "o3", "primary", Decimal(6), "active"),
        ],
        "faculty_name": {F1: "A. Rao", F2: "B. Iyer"}.__getitem__,
        "max_weekly_contact_hours": 18,
        **kwargs,
    }
    return faculty_load_report(Actor("u1", "org1", permissions={FACULTY_LOAD_READ}), **values)


# --- accepts the use case's output


@pytest.mark.parametrize("kwargs", [{}, {"department_id": DEPT}, {"over_load_only": True}, {"entries": []}])
def test_the_schema_accepts_the_use_case_output_unchanged(kwargs):
    body = use_case_output(**kwargs)
    assert FacultyLoadReportOut.model_validate(body).model_dump(mode="json") == body


def test_department_may_be_null_or_left_out():
    body = use_case_output()
    assert body["department_id"] is None
    body.pop("department_id")
    assert FacultyLoadReportOut.model_validate(body).department_id is None


# --- mirrors the contract


@pytest.mark.parametrize(
    ("model", "name"), [(FacultyLoadReportOut, "FacultyLoadReport"), (FacultyLoadOut, "FacultyLoad")]
)
def test_fields_and_required_fields_match_the_contract(model, name):
    generated = model.model_json_schema()
    assert set(generated["properties"]) == set(SCHEMAS[name]["properties"])
    assert set(generated.get("required", [])) == set(SCHEMAS[name]["required"])


# --- rejects what the contract does not allow


def item(**changes) -> dict:
    return {**use_case_output()["items"][0], **changes}


@pytest.mark.parametrize(
    "changes",
    [
        {"faculty_name": None},
        {"faculty_id": "f1"},  # not a uuid
        {"offerings_count": True},  # a boolean is not an integer
        {"offerings_count": "2"},
        {"contact_hours": "19.5"},  # a string is not a number
        {"over_load": "yes"},
        {"over_load": 1},
        {"rank": 1},  # not in the contract
    ],
)
def test_an_invalid_item_is_rejected(changes):
    with pytest.raises(ValidationError):
        FacultyLoadOut.model_validate(item(**changes))


def test_an_item_without_its_required_name_is_rejected():
    body = item()
    body.pop("faculty_name")
    with pytest.raises(ValidationError):
        FacultyLoadOut.model_validate(body)


@pytest.mark.parametrize(
    "changes",
    [
        {"academic_period_id": "p1"},
        {"department_id": "d1"},
        {"academic_period_code": None},
        {"faculty_count": -1},
        {"over_load_count": -1},
        {"faculty_count": 2.0},
        {"max_weekly_contact_hours": "18"},
        {"items": "none"},
        {"generated_at": "2026-10-16T00:00:00Z"},  # not in the contract
    ],
)
def test_an_invalid_report_is_rejected(changes):
    with pytest.raises(ValidationError):
        FacultyLoadReportOut.model_validate({**use_case_output(), **changes})


@pytest.mark.parametrize("field", ["academic_period_name", "max_weekly_contact_hours", "faculty_count", "items"])
def test_a_report_missing_a_required_field_is_rejected(field):
    body = use_case_output()
    body.pop(field)
    with pytest.raises(ValidationError):
        FacultyLoadReportOut.model_validate(body)
