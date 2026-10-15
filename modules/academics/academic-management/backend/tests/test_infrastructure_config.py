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


@pytest.mark.parametrize("raw", ["-1", "NaN", "Infinity"])
def test_negative_or_non_finite_values_are_refused(monkeypatch, raw):
    monkeypatch.setenv(MAX_WEEKLY_CONTACT_HOURS_KEY, raw)
    with pytest.raises(DomainRuleError):
        load_settings()
