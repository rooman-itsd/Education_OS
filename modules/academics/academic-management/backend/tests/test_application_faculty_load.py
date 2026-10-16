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


# --- statuses: only what getFacultyLoad declares


def test_the_use_case_only_answers_with_statuses_the_contract_declares():
    declared = {int(code) for code in CONTRACT["paths"]["/faculty-load"]["get"]["responses"]}
    raised = set()
    for kwargs in ({"actor": Actor("u2", "org1")}, {"period": None}):
        with pytest.raises(AcademicManagementError) as err:
            report(**kwargs)
        raised.add(err.value.status)
    assert raised == {403, 404}
    assert raised | {200} <= declared


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_weekly_contact_hours": -1},
        {"max_weekly_contact_hours": "18"},
        {"max_weekly_contact_hours": float("nan")},
        {"entries": [LoadEntry("f1", "o1", "lecturer", Decimal(1), "active")]},
        {"entries": [LoadEntry("f1", "o1", "primary", Decimal(-2), "active")]},
        {"entries": [LoadEntry("f1", "o1", "primary", Decimal(2), "paused")]},
    ],
)
def test_invalid_stored_data_or_settings_are_server_faults_not_400(kwargs):
    # Rows and the maximum come from storage and settings, not the request; the contract declares no 400 here.
    with pytest.raises(ValueError, match="invalid faculty-load data"):
        report(**kwargs)


# --- edge cases


def test_a_term_without_counted_load_gives_an_empty_report():
    body = report(entries=[LoadEntry("f1", "o1", "teaching_assistant", Decimal(4), "active")])
    assert (body["items"], body["faculty_count"], body["over_load_count"]) == ([], 0, 0)
    assert body["academic_period_id"] == "p1"


def test_over_load_only_with_nobody_over_load_lists_nobody_but_keeps_the_count():
    body = report(over_load_only=True, max_weekly_contact_hours=40)
    assert (body["items"], body["faculty_count"], body["over_load_count"]) == ([], 2, 0)


@pytest.mark.parametrize(("maximum", "echoed"), [(18, 18), (Decimal("18.0"), 18), (17.5, 17.5), (Decimal("0"), 0)])
def test_the_report_echoes_the_maximum_it_compared_against(maximum, echoed):
    body = report(max_weekly_contact_hours=maximum)
    assert body["max_weekly_contact_hours"] == echoed
    assert type(body["max_weekly_contact_hours"]) is type(echoed)


def test_exactly_at_the_maximum_is_not_over_load():
    body = report(entries=[LoadEntry("f1", "o1", "primary", Decimal(18), "active")])
    assert (body["items"][0]["over_load"], body["over_load_count"]) == (False, 0)


def test_a_name_lookup_that_fails_is_not_hidden():
    with pytest.raises(KeyError):
        report(faculty_name={}.__getitem__)


@pytest.mark.parametrize("name", [None, 42])
def test_a_name_that_is_not_a_string_is_a_server_fault(name):
    with pytest.raises(ValueError, match="no display name"):
        report(faculty_name=lambda _fid: name)


# --- contract drift: value types, not only field names

JSON_TYPES = {
    "string": (str,),
    "integer": (int,),
    "number": (int, float),
    "boolean": (bool,),
    "array": (list,),
    "object": (dict,),
    "null": (type(None),),
}


def assert_matches(value, schema):
    if "$ref" in schema:
        schema = SCHEMAS[schema["$ref"].rsplit("/", 1)[1]]
    types = schema.get("type")
    allowed = types if isinstance(types, list) else [types]
    ok = any(isinstance(value, JSON_TYPES[t]) for t in allowed)
    if isinstance(value, bool) and "boolean" not in allowed:
        ok = False  # bool is an int in Python, never a JSON integer or number
    assert ok, (value, schema)
    if isinstance(value, dict):
        for key, item in value.items():
            assert_matches(item, schema["properties"][key])
    if isinstance(value, list):
        for item in value:
            assert_matches(item, schema["items"])
    if "minimum" in schema:
        assert value >= schema["minimum"]


@pytest.mark.parametrize("kwargs", [{}, {"department_id": "d1"}, {"over_load_only": True}, {"entries": []}])
def test_every_value_has_the_type_the_contract_declares(kwargs):
    assert_matches(report(**kwargs), SCHEMAS["FacultyLoadReport"])
