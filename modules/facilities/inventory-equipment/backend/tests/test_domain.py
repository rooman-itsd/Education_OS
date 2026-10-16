"""Unit tests of the pure inventory rules (domain layer)."""

from datetime import UTC, datetime, timedelta

import pytest
from eos_inventory_equipment.domain.rules import (
    LoanRules,
    RuleViolationError,
    StockShortageError,
    check_due,
    check_loan_line,
    check_open_loans,
    days_late,
    effective_rules,
    loan_status,
    low_stock_transition,
    take,
)

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)


def line(**overrides):
    args = {
        "rules": LoanRules(),
        "loanable": True,
        "consumable": False,
        "active": True,
        "quantity": 1,
        "roles": set(),
        "manage": False,
    } | overrides
    check_loan_line(**args)


def test_effective_rules_fall_back_item_over_category():
    rules = effective_rules(
        LoanRules(max_loan_days=14),
        {"max_loan_days": 7, "requires_approval": True},
        {"max_loan_days": None, "borrower_role_ids": ["a"]},
    )
    assert rules == LoanRules(requires_approval=True, max_loan_days=7, borrower_role_ids=("a",))


@pytest.mark.parametrize(
    ("overrides", "code"),
    [
        ({"consumable": True}, "consumable_not_loanable"),
        ({"loanable": False}, "not_loanable"),
        ({"active": False}, "not_loanable"),
        ({"rules": LoanRules(borrower_role_ids=("senior",))}, "not_loanable"),
        ({"rules": LoanRules(max_quantity_per_loan=2), "quantity": 3}, "too_many_items"),
    ],
)
def test_loan_line_rules(overrides, code):
    with pytest.raises(RuleViolationError) as e:
        line(**overrides)
    assert e.value.code == code


def test_managers_skip_role_restrictions():
    line(rules=LoanRules(borrower_role_ids=("senior",)), manage=True)


def test_due_dates_and_open_loan_limit():
    check_due(NOW + timedelta(days=3), NOW, 14)
    with pytest.raises(RuleViolationError, match="future"):
        check_due(NOW, NOW, 14)
    with pytest.raises(RuleViolationError) as e:
        check_due(NOW + timedelta(days=15), NOW, 14)
    assert (e.value.code, e.value.limit) == ("too_long", 14)
    with pytest.raises(RuleViolationError) as e:
        check_open_loans(3, 3)
    assert e.value.code == "too_many_open_loans"


def test_stock_never_goes_negative():
    assert take(5, 2) == 3
    with pytest.raises(StockShortageError) as e:
        take(1, 2)
    assert (e.value.available, e.value.requested) == (1, 2)


def test_low_stock_is_published_once_per_crossing():
    assert low_stock_transition(2, 2, currently_low=False) == "low"
    assert low_stock_transition(1, 2, currently_low=True) is None
    assert low_stock_transition(3, 2, currently_low=True) == "replenished"
    assert low_stock_transition(3, None, currently_low=False) is None


def test_loan_status_from_lines():
    due = NOW + timedelta(days=1)
    assert loan_status(["out", "out"], due, NOW) == "on_loan"
    assert loan_status(["out", "returned"], due, NOW) == "partially_returned"
    assert loan_status(["out"], due, NOW + timedelta(days=2)) == "overdue"
    assert loan_status(["returned", "returned"], due, NOW) == "returned"
    assert loan_status(["returned", "lost"], due, NOW) == "closed_with_loss"


def test_days_late_counts_started_days():
    assert days_late(NOW, NOW) == 0
    assert days_late(NOW, NOW + timedelta(hours=1)) == 1
    assert days_late(NOW, NOW + timedelta(days=2)) == 2
