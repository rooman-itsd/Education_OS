"""Unit tests of the module settings: ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS (config/env.example, FR-13)."""

from decimal import Decimal

import pytest
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.infrastructure.config import MAX_WEEKLY_CONTACT_HOURS_KEY, load_settings


def test_default_is_the_documented_18(monkeypatch):
    monkeypatch.delenv(MAX_WEEKLY_CONTACT_HOURS_KEY, raising=False)
    assert load_settings().max_weekly_contact_hours == Decimal(18)


@pytest.mark.parametrize(("raw", "expected"), [("20", Decimal(20)), (" 17.5 ", Decimal("17.5")), ("", Decimal(18))])
def test_value_is_read_on_every_call(monkeypatch, raw, expected):
    monkeypatch.setenv(MAX_WEEKLY_CONTACT_HOURS_KEY, raw)
    assert load_settings().max_weekly_contact_hours == expected


def test_a_value_that_is_not_a_number_is_a_configuration_error(monkeypatch):
    monkeypatch.setenv(MAX_WEEKLY_CONTACT_HOURS_KEY, "eighteen")
    with pytest.raises(ValueError, match=MAX_WEEKLY_CONTACT_HOURS_KEY):
        load_settings()


@pytest.mark.parametrize("raw", ["-1", "-0.5", "NaN", "Infinity", "-Infinity", "1e400"])
def test_negative_non_finite_or_huge_values_are_configuration_errors(monkeypatch, raw):
    # A deployment error, not a domain error an API layer could report to a caller as a bad request.
    monkeypatch.setenv(MAX_WEEKLY_CONTACT_HOURS_KEY, raw)
    with pytest.raises(ValueError, match=MAX_WEEKLY_CONTACT_HOURS_KEY) as err:
        load_settings()
    assert not isinstance(err.value, DomainRuleError)


@pytest.mark.parametrize(("raw", "expected"), [("0", Decimal(0)), ("1e2", Decimal(100)), ("18.25", Decimal("18.25"))])
def test_boundary_and_exponent_values_are_accepted(monkeypatch, raw, expected):
    monkeypatch.setenv(MAX_WEEKLY_CONTACT_HOURS_KEY, raw)
    assert load_settings().max_weekly_contact_hours == expected
