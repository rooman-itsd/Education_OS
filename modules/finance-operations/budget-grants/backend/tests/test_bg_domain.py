"""Pure budget rules."""

from datetime import date
from decimal import Decimal

import pytest
from eos_budget_grants.domain import rules
from eos_budget_grants.domain.rules import RuleError

D = Decimal


def test_money():
    assert rules.money("10") == "10.00"
    assert rules.parse_money("0", positive=False) == D("0.00")
    for bad in ("0", "-1", "1.234", "x"):
        with pytest.raises(RuleError):
            rules.parse_money(bad)


def test_available_and_used():
    assert rules.available(D("100"), D("30"), D("50")) == D("20.00")
    assert rules.used_percent(D("100"), D("30"), D("50")) == D(80)
    assert rules.used_percent(D("0"), D("0"), D("1")) == D(100)
    assert rules.used_percent(D("0"), D("0"), D("0")) == D(0)
    assert rules.thresholds_crossed(D("85"), [100, 80]) == [80]
    assert rules.thresholds_crossed(D("100"), [80, 100]) == [80, 100]


def test_financial_years():
    assert rules.financial_year_of(date(2026, 10, 23), 4) == "2026-27"
    assert rules.financial_year_of(date(2027, 3, 31), 4) == "2026-27"
    assert rules.financial_year_of(date(2027, 4, 1), 4) == "2027-28"
    assert rules.financial_year_bounds("2026-27", 4) == (date(2026, 4, 1), date(2027, 3, 31))
    assert rules.financial_year_bounds("2026-27", 1) == (date(2026, 1, 1), date(2026, 12, 31))
    with pytest.raises(RuleError):
        rules.financial_year_bounds("this year", 4)


def test_add_months_keeps_month_ends_valid():
    assert rules.add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert rules.add_months(date(2026, 11, 15), 3) == date(2027, 2, 15)


def test_certificate_due_dates():
    start, end = date(2026, 4, 1), date(2028, 3, 31)
    assert rules.uc_due_dates(start, end, "yearly") == [date(2027, 3, 31), date(2028, 3, 31)]
    assert rules.uc_due_dates(start, end, "half_yearly")[:2] == [date(2026, 9, 30), date(2027, 3, 31)]
    assert rules.uc_due_dates(start, end, "on_completion") == [end]
    assert rules.next_uc_due(start, end, "yearly", None) == date(2027, 3, 31)
    assert rules.next_uc_due(start, end, "yearly", date(2027, 3, 31)) == date(
        2028, 3, 31
    )  # a certificate to the period end covers it
    assert rules.next_uc_due(start, end, "yearly", date(2028, 3, 31)) is None
