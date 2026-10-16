"""Unit tests of the programme rules (domain layer): FR-3 and contract CreateProgrammeRequest."""

from decimal import Decimal

import pytest
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.programmes import ARCHIVED, PROGRAMME_LEVELS, archive, validate_programme


@pytest.mark.parametrize("level", PROGRAMME_LEVELS)
def test_every_contract_level_is_accepted(level):
    assert validate_programme(level=level, duration_terms=6, credits_required=120).level == level


def test_valid_programme_keeps_exact_credits():
    shape = validate_programme(level="undergraduate", duration_terms=1, credits_required=0)
    assert (shape.duration_terms, shape.credits_required) == (1, Decimal(0))
    assert validate_programme(level="diploma", duration_terms=4, credits_required=60.5).credits_required == Decimal(
        "60.5"
    )


@pytest.mark.parametrize(
    ("kwargs", "code", "field"),
    [
        ({"level": "bachelor"}, "invalid_choice", "level"),
        ({"duration_terms": 0}, "below_minimum", "duration_terms"),
        ({"duration_terms": 2.5}, "invalid_integer", "duration_terms"),
        ({"duration_terms": True}, "invalid_integer", "duration_terms"),
        ({"credits_required": -1}, "below_minimum", "credits_required"),
        ({"credits_required": float("nan")}, "invalid_number", "credits_required"),
        ({"credits_required": "120"}, "invalid_number", "credits_required"),
    ],
)
def test_invalid_programme_values(kwargs, code, field):
    values = {"level": "undergraduate", "duration_terms": 6, "credits_required": 120, **kwargs}
    with pytest.raises(DomainRuleError) as err:
        validate_programme(**values)
    assert (err.value.code, err.value.field, err.value.kind) == (code, field, "invalid")


@pytest.mark.parametrize("status", ["active", "archived"])
def test_archiving_ends_archived_and_is_idempotent(status):
    assert archive(status) == ARCHIVED


def test_archiving_rejects_an_unknown_status():
    with pytest.raises(DomainRuleError):
        archive("deleted")


def test_decimal_credits_are_accepted_exactly():
    assert validate_programme(level="diploma", duration_terms=2, credits_required=Decimal("60.5")).credits_required == (
        Decimal("60.5")
    )


@pytest.mark.parametrize("value", [Decimal("NaN"), Decimal("Infinity"), 10**400])
def test_programme_credits_reject_non_finite_and_huge_values(value):
    with pytest.raises(DomainRuleError) as err:
        validate_programme(level="diploma", duration_terms=2, credits_required=value)
    assert err.value.field == "credits_required"
