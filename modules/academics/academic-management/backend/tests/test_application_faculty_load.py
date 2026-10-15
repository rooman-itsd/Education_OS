"""Unit tests of GET /faculty-load (application layer): the FacultyLoadReport shape of contracts/openapi.yaml,
the 403 and 404 responses, and the owner decisions on PR #168."""

from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
import yaml
from eos_academic_management.application.access import FACULTY_LOAD_READ, Actor
from eos_academic_management.application.errors import AcademicManagementError
from eos_academic_management.application.faculty_load import faculty_load_report
from eos_academic_management.domain.load import LoadEntry
from eos_academic_management.domain.terms import ACTIVE, DateRange, Term

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "openapi.yaml").read_text(encoding="utf-8")
)
SCHEMAS = CONTRACT["components"]["schemas"]

HOD = Actor("u1", "org1", roles=["department-admin"], permissions={FACULTY_LOAD_READ})
ODD = Term("p1", "2026-ODD", "Odd Semester 2026", DateRange(date(2026, 7, 1), date(2026, 11, 30)), ACTIVE)
NAMES = {"f1": "A. Rao", "f2": "B. Iyer", "f3": "C. Das"}

ENTRIES = [
    LoadEntry("f1", "o1", "primary", Decimal(12), "active"),
    LoadEntry("f1", "o2", "co_instructor", Decimal("7.5"), "active"),
    LoadEntry("f2", "o1", "teaching_assistant", Decimal(10), "active"),
    LoadEntry("f2", "o3", "primary", Decimal(6), "active"),
    LoadEntry("f3", "o4", "primary", Decimal(20), "ended"),
]


def report(**kwargs):
    values = {
        "period": ODD,
        "entries": ENTRIES,
        "faculty_name": NAMES.__getitem__,
        "max_weekly_contact_hours": 18,
        **kwargs,
    }
    return faculty_load_report(values.pop("actor", HOD), **values)


def test_report_has_every_field_the_contract_requires():
    body = report()
    assert set(SCHEMAS["FacultyLoadReport"]["required"]) <= set(body)
    for item in body["items"]:
        assert set(SCHEMAS["FacultyLoad"]["required"]) <= set(item)


def test_report_has_no_field_the_contract_does_not_define():
    body = report()
    assert set(body) <= set(SCHEMAS["FacultyLoadReport"]["properties"])
    for item in body["items"]:
        assert set(item) <= set(SCHEMAS["FacultyLoad"]["properties"])


def test_report_names_the_term_and_lists_counted_load_over_load_first():
    body = report(department_id="d1")
    assert {k: body[k] for k in ("academic_period_id", "academic_period_code", "academic_period_name")} == {
        "academic_period_id": "p1",
        "academic_period_code": "2026-ODD",
        "academic_period_name": "Odd Semester 2026",
    }
    assert (body["department_id"], body["max_weekly_contact_hours"]) == ("d1", 18)
    assert body["items"] == [
        {"faculty_id": "f1", "faculty_name": "A. Rao", "offerings_count": 2, "contact_hours": 19.5, "over_load": True},
        # f2's teaching-assistant hours are left out; f3's only assignment has ended
        {"faculty_id": "f2", "faculty_name": "B. Iyer", "offerings_count": 1, "contact_hours": 6, "over_load": False},
    ]
    assert (body["faculty_count"], body["over_load_count"]) == (2, 1)


def test_over_load_only_keeps_the_counts():
    body = report(over_load_only=True)
    assert [item["faculty_id"] for item in body["items"]] == ["f1"]
    assert (body["faculty_count"], body["over_load_count"]) == (2, 1)


def test_department_is_used_as_given():
    assert report()["department_id"] is None


def test_no_term_is_404_active_term_not_found():
    with pytest.raises(AcademicManagementError) as err:
        report(period=None)
    assert (err.value.status, err.value.code) == (404, "active_term_not_found")


def test_caller_without_the_key_is_forbidden_before_anything_else():
    with pytest.raises(AcademicManagementError) as err:
        report(actor=Actor("u2", "org1"), period=None)
    assert err.value.status == 403


def test_names_are_resolved_only_for_listed_rows():
    asked = []
    report(faculty_name=lambda fid: asked.append(fid) or NAMES[fid], over_load_only=True)
    assert asked == ["f1"]


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"max_weekly_contact_hours": -1}, "below_minimum"),
        ({"entries": [LoadEntry("f1", "o1", "lecturer", Decimal(1), "active")]}, "invalid_choice"),
    ],
)
def test_invalid_inputs_are_400(kwargs, code):
    with pytest.raises(AcademicManagementError) as err:
        report(**kwargs)
    assert (err.value.status, err.value.code) == (400, code)
