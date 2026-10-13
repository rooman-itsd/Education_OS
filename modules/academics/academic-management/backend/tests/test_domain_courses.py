"""Unit tests of the course rules (domain layer): FR-6, FR-7 and contract CreateCourseRequest."""

from decimal import Decimal

import pytest
from eos_academic_management.domain.courses import ARCHIVED, COURSE_TYPES, archive, validate_course
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.values import ensure_unique_code


@pytest.mark.parametrize("course_type", COURSE_TYPES)
def test_every_contract_course_type_is_accepted(course_type):
    assert validate_course(credits=4, course_type=course_type).course_type == course_type


def test_contact_hours_are_optional_and_may_be_zero():
    shape = validate_course(credits=0, course_type="theory")
    assert (shape.credits, shape.lecture_hours, shape.practical_hours) == (Decimal(0), None, None)
    shape = validate_course(credits=3, course_type="practical", lecture_hours=0, practical_hours=2.5)
    assert (shape.lecture_hours, shape.practical_hours) == (Decimal(0), Decimal("2.5"))


@pytest.mark.parametrize(
    ("kwargs", "code", "field"),
    [
        ({"credits": -0.5}, "below_minimum", "credits"),
        ({"course_type": "lab"}, "invalid_choice", "course_type"),
        ({"lecture_hours": -1}, "below_minimum", "lecture_hours"),
        ({"practical_hours": float("inf")}, "invalid_number", "practical_hours"),
    ],
)
def test_invalid_course_values(kwargs, code, field):
    values = {"credits": 4, "course_type": "theory", **kwargs}
    with pytest.raises(DomainRuleError) as err:
        validate_course(**values)
    assert (err.value.code, err.value.field, err.value.kind) == (code, field, "invalid")


def test_course_code_must_be_unique_in_the_organisation():
    ensure_unique_code("CS101", ["CS102", "MA101"])
    with pytest.raises(DomainRuleError) as err:
        ensure_unique_code("CS101", ["CS101"])
    assert (err.value.code, err.value.kind, err.value.field) == ("duplicate_code", "conflict", "code")


def test_code_comparison_is_exact():
    ensure_unique_code("cs101", ["CS101"])  # case-insensitivity is an open question, not assumed


@pytest.mark.parametrize("status", ["active", "archived"])
def test_archiving_ends_archived_and_is_idempotent(status):
    assert archive(status) == ARCHIVED


def test_decimal_values_are_accepted_exactly():
    shape = validate_course(credits=Decimal("3"), course_type="studio", lecture_hours=Decimal("1.5"))
    assert (shape.credits, shape.lecture_hours) == (Decimal("3"), Decimal("1.5"))


@pytest.mark.parametrize("value", [Decimal("-Infinity"), Decimal("NaN")])
def test_decimal_non_finite_values_are_rejected(value):
    with pytest.raises(DomainRuleError) as err:
        validate_course(credits=value, course_type="theory")
    assert (err.value.code, err.value.field) == ("invalid_number", "credits")


def test_archiving_rejects_an_unknown_status():
    with pytest.raises(DomainRuleError) as err:
        archive("deleted")
    assert (err.value.code, err.value.field) == ("invalid_choice", "status")
