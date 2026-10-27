"""Unit tests of the pure asset-management rules (domain layer)."""

from datetime import date
from decimal import Decimal

import pytest
from eos_asset_management.domain.rules import (
    Depreciation,
    RuleViolationError,
    add_months,
    check_cancel,
    check_close,
    check_complete,
    check_decision,
    check_depreciation,
    check_disposal_request,
    check_line,
    check_manual_status,
    depreciate,
    due_state,
    effective_depreciation,
    money,
    month_ends,
    monthly_charge,
    next_verification_due,
    project,
    residual_value,
    run_period,
    tag_for,
    transfer_changes,
)

TODAY = date(2026, 10, 12)
SL = Depreciation(method="straight_line", useful_life_months=60, residual_percent=5)
WDV = Depreciation(method="written_down_value", rate_percent=12, residual_percent=5)


def test_asset_settings_override_the_category_and_nothing_means_none():
    d = effective_depreciation({"method": "straight_line", "useful_life_months": 60}, {"useful_life_months": 36})
    assert (d.method, d.useful_life_months, d.residual_percent) == ("straight_line", 36, 5.0)
    assert effective_depreciation(None, None).method == "none"
    with pytest.raises(RuleViolationError):
        check_depreciation(Depreciation(method="straight_line"))
    with pytest.raises(RuleViolationError):
        check_depreciation(Depreciation(method="written_down_value"))


def test_straight_line_charges_evenly_and_stops_at_residual():
    cost = Decimal("60000.00")
    assert residual_value(cost, SL) == Decimal("3000.00")
    assert monthly_charge(SL, cost, cost) == Decimal("950.00")  # (60000 - 3000) / 60
    assert monthly_charge(SL, cost, Decimal("3500.00")) == Decimal("500.00")  # only the room above residual
    assert monthly_charge(SL, cost, Decimal("3000.00")) == Decimal("0")


def test_written_down_value_charges_a_share_of_book_value():
    cost = Decimal("100000.00")
    assert monthly_charge(WDV, cost, cost) == Decimal("1000.00")  # 12% a year, one month
    assert monthly_charge(WDV, cost, Decimal("50000.00")) == Decimal("500.00")
    assert monthly_charge(Depreciation(method="none"), cost, cost) == Decimal("0")


def test_depreciation_is_pro_rated_from_the_month_in_service():
    cost = Decimal("60000.00")
    months = month_ends(date(2026, 7, 1), date(2026, 9, 30))
    total, closing, steps = depreciate(SL, cost, cost, date(2026, 8, 20), months)
    assert [m for m, _, _ in steps] == [date(2026, 8, 31), date(2026, 9, 30)]  # July is before service
    assert total == Decimal("1900.00") and closing == Decimal("58100.00")


def test_projection_runs_until_residual():
    cost = Decimal("1200.00")
    plan = project(
        Depreciation(method="straight_line", useful_life_months=12, residual_percent=0),
        cost,
        cost,
        date(2026, 1, 15),
        None,
    )
    assert len(plan) == 12
    assert plan[-1] == (date(2026, 12, 31), Decimal("100.00"), Decimal("0.00"))
    after = project(SL, Decimal("60000.00"), Decimal("59050.00"), date(2026, 1, 1), date(2026, 1, 31))
    assert after[0][0] == date(2026, 2, 28)


def test_run_periods_follow_the_last_posted_period():
    assert run_period(date(2026, 9, 30), None) == date(2026, 9, 1)
    assert run_period(date(2026, 12, 31), date(2026, 9, 30)) == date(2026, 10, 1)
    with pytest.raises(RuleViolationError) as e:
        run_period(date(2026, 9, 30), date(2026, 9, 30))
    assert e.value.status == 409
    with pytest.raises(RuleViolationError):
        run_period(date(2026, 9, 15), None)


def test_dates_and_month_ends():
    assert add_months(date(2026, 1, 31), 1) == date(2026, 2, 28)
    assert month_ends(date(2026, 11, 10), date(2027, 1, 5)) == [
        date(2026, 11, 30),
        date(2026, 12, 31),
        date(2027, 1, 31),
    ]


def test_verification_due_dates_and_windows():
    assert next_verification_due(None, date(2025, 10, 1), 12) == date(2026, 10, 1)
    assert next_verification_due(date(2026, 3, 1), date(2025, 1, 1), 6) == date(2026, 9, 1)
    assert due_state(date(2026, 10, 1), TODAY, 30) == "overdue"
    assert due_state(date(2026, 11, 11), TODAY, 30) == "due_soon"
    assert due_state(date(2026, 11, 12), TODAY, 30) is None


def test_status_changes_outside_disposal_only():
    check_manual_status("in_service", "in_repair")
    with pytest.raises(RuleViolationError) as e:
        check_manual_status("disposal_pending", "in_service")
    assert e.value.status == 409
    with pytest.raises(RuleViolationError):
        check_manual_status("in_service", "disposed")


def test_transfers_record_only_what_changes():
    current = {"location": "Lab 1", "org_unit_id": "d1", "custodian_id": "u1"}
    assert transfer_changes(current, {"location": "Lab 2", "custodian_id": "u1"}) == (
        {"location": "Lab 1"},
        {"location": "Lab 2"},
    )
    with pytest.raises(RuleViolationError):
        transfer_changes(current, {"location": "Lab 1"})


def test_verification_lines_and_closing():
    check_line("found", None)
    with pytest.raises(RuleViolationError):
        check_line("relocated", " ")
    check_close(0, False)
    check_close(3, True)
    with pytest.raises(RuleViolationError):
        check_close(3, False)


def test_disposal_steps():
    with pytest.raises(RuleViolationError):
        check_disposal_request("disposal_pending")
    check_decision("requested", "u1", "u2")
    with pytest.raises(RuleViolationError) as e:
        check_decision("requested", "u1", "u1")
    assert e.value.code == "own_request"
    check_cancel("approved")
    with pytest.raises(RuleViolationError):
        check_cancel("completed")
    with pytest.raises(RuleViolationError):
        check_complete("requested")


def test_money_and_tags():
    assert money("-150.25", "INR", allow_negative=True) == Decimal("-150.25")
    with pytest.raises(RuleViolationError):
        money("-1", "INR")
    with pytest.raises(RuleViolationError):
        money("1.005", "INR")
    assert tag_for("AST", "IT", 7) == "AST-IT-00007"
    assert tag_for("AST", None, 12) == "AST-00012"
