"""Unit tests of the shared validators and the domain error type.

Accepted numeric inputs (values.NUMBER_TYPES): int, float and Decimal. bool, str, Fraction and other types
are rejected; NaN and infinities are rejected; magnitudes beyond a finite IEEE 754 double are rejected."""

from decimal import Decimal
from fractions import Fraction

import pytest
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.values import (
    MAX_MAGNITUDE,
    ensure_unique_code,
    require_choice,
    require_integer,
    require_number,
)


def code_of(fn):
    with pytest.raises(DomainRuleError) as err:
        fn()
    return err.value.code


# --- numbers


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, Decimal(0)),
        (3, Decimal(3)),
        (2.25, Decimal("2.25")),
        (0.1, Decimal("0.1")),  # through repr, not the binary expansion
        (Decimal("3"), Decimal("3")),
        (Decimal("0.1"), Decimal("0.1")),
        (Decimal("2.50"), Decimal("2.50")),  # Decimal kept as given
    ],
)
def test_accepted_numbers_are_exact(value, expected):
    result = require_number(value, "x", minimum=0)
    assert result == expected and isinstance(result, Decimal)


def test_decimal_inputs_keep_exact_arithmetic():
    total = require_number(Decimal("0.1"), "x", minimum=0) + require_number(Decimal("0.2"), "x", minimum=0)
    assert total == Decimal("0.3")


def test_int_float_and_decimal_agree():
    assert (
        require_number(3, "x", minimum=0)
        == require_number(3.0, "x", minimum=0)
        == require_number(Decimal("3"), "x", minimum=0)
    )


@pytest.mark.parametrize(
    "value",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        Decimal("NaN"),
        Decimal("sNaN"),
        Decimal("Infinity"),
        Decimal("-Infinity"),
    ],
)
def test_nan_and_infinities_are_controlled_errors(value):
    assert code_of(lambda: require_number(value, "x", minimum=0)) == "invalid_number"


@pytest.mark.parametrize("value", [True, False, "3", None, Fraction(1, 3), [1], object()])
def test_unsupported_types_are_controlled_errors(value):
    assert code_of(lambda: require_number(value, "x", minimum=0)) == "invalid_number"


@pytest.mark.parametrize("value", [10**400, -(10**400), Decimal("1E+400")])
def test_huge_magnitudes_are_controlled_errors(value):
    assert code_of(lambda: require_number(value, "x", minimum=0)) == "number_out_of_range"


def test_largest_finite_double_is_still_accepted():
    assert require_number(1.7976931348623157e308, "x", minimum=0) <= MAX_MAGNITUDE


@pytest.mark.parametrize("value", [-0.01, Decimal("-0.01"), -1])
def test_below_minimum(value):
    assert code_of(lambda: require_number(value, "x", minimum=0)) == "below_minimum"


def test_integer_rejects_floats_booleans_and_decimals():
    assert require_integer(1, "x", minimum=1) == 1
    for bad in (1.0, False, Decimal(1), "1"):
        assert code_of(lambda bad=bad: require_integer(bad, "x", minimum=0)) == "invalid_integer"
    assert code_of(lambda: require_integer(0, "x", minimum=1)) == "below_minimum"


def test_choice():
    assert require_choice("a", "x", ("a", "b")) == "a"
    assert code_of(lambda: require_choice(None, "x", ("a", "b"))) == "invalid_choice"


# --- codes


def test_code_must_be_a_string():
    for bad in (None, 101, b"CS101"):
        with pytest.raises(DomainRuleError) as err:
            ensure_unique_code(bad, ["CS101"])
        assert (err.value.code, err.value.kind, err.value.field) == ("invalid_code", "invalid", "code")


def test_code_comparison_is_case_sensitive_as_currently_specified():
    ensure_unique_code("cs101", ["CS101"])  # case-insensitivity is an open question, not assumed
    assert code_of(lambda: ensure_unique_code("CS101", ("CS101",))) == "duplicate_code"


def test_uniqueness_applies_to_the_codes_passed_in():
    ensure_unique_code("BSC-CS", [])  # the caller passes one organisation's codes
    assert code_of(lambda: ensure_unique_code("BSC-CS", iter(["MSC", "BSC-CS"]))) == "duplicate_code"


# --- errors


def test_error_kind_must_be_known():
    with pytest.raises(ValueError):
        DomainRuleError("c", "m", kind="teapot")
