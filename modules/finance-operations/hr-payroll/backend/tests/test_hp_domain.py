"""The pure rules: exact money, leave days and years, carry-forward, periods and the payslip with loss of pay."""

from datetime import date
from decimal import Decimal

import pytest
from eos_hr_payroll.domain import rules
from eos_hr_payroll.domain.rules import RuleError


def test_money_is_exact_and_bounded():
    assert rules.parse_money("10.5") == Decimal("10.50")
    assert rules.money(Decimal("0.005")) == "0.01"
    for bad in ("1.234", "abc", "0", "-1", "1000000000000"):
        with pytest.raises(RuleError):
            rules.parse_money(bad)


def test_bank_account_ifsc_and_pan_keep_only_what_is_allowed():
    assert rules.account_last4("1234 5678 9012") == "9012"
    assert rules.check_ifsc(" sbin0001234 ") == "SBIN0001234"
    assert rules.pan_last4("abcde1234f") == "234F"
    assert rules.pan_masked("234F") == "XXXXXX234F"
    for fn, bad in ((rules.account_last4, "12345"), (rules.check_ifsc, "SBIN1001234"), (rules.pan_last4, "ABCD1234FF")):
        with pytest.raises(RuleError) as err:
            fn(bad)
        assert bad not in err.value.message


def test_leave_days_count_calendar_days_and_half_days():
    assert rules.leave_days(date(2026, 11, 2), date(2026, 11, 6)) == 5
    assert rules.leave_days(date(2026, 11, 2), date(2026, 11, 2), "first_half") == Decimal("0.5")
    with pytest.raises(RuleError):
        rules.leave_days(date(2026, 11, 2), date(2026, 11, 3), "first_half")
    with pytest.raises(RuleError):
        rules.leave_days(date(2026, 11, 3), date(2026, 11, 2))


def test_leave_years_follow_the_start_month():
    assert rules.leave_year(date(2027, 3, 31), 4) == 2026
    assert rules.leave_year(date(2027, 4, 1), 4) == 2027
    assert rules.leave_year_bounds(2026, 4) == (date(2026, 4, 1), date(2027, 3, 31))


def test_entitlement_is_a_share_in_the_year_of_joining():
    assert rules.entitlement(Decimal(12), date(2020, 1, 1), 2026, 1) == 12
    assert rules.entitlement(Decimal(12), date(2026, 10, 15), 2026, 1) == 3  # Oct, Nov, Dec
    assert rules.entitlement(Decimal(10), date(2026, 8, 1), 2026, 1) == Decimal("4")  # 10 * 5 / 12 = 4.16 -> 4
    assert rules.entitlement(Decimal(15), date(2026, 8, 1), 2026, 1) == Decimal("6")  # 6.25 -> 6
    assert rules.entitlement(Decimal(12), date(2027, 2, 1), 2026, 1) == 0


def test_carry_forward_is_capped_and_never_negative():
    assert rules.carried_into_next_year(Decimal(12), Decimal(0), Decimal(4), Decimal(5)) == 5
    assert rules.carried_into_next_year(Decimal(12), Decimal(2), Decimal(12), Decimal(5)) == 2
    assert rules.carried_into_next_year(Decimal(12), Decimal(0), Decimal(14), Decimal(5)) == 0


def test_periods_and_due_days():
    assert rules.parse_period("2026-02") == (date(2026, 2, 1), date(2026, 2, 28))
    assert rules.due_on("2026-02", 30) == date(2026, 2, 28)
    for bad in ("2026-13", "2026-1", "26-01", ""):
        with pytest.raises(RuleError):
            rules.parse_period(bad)


def test_employed_days_cover_joining_and_exit():
    first, last = date(2026, 10, 1), date(2026, 10, 31)
    assert rules.employed_days(first, last, date(2020, 1, 1), None) == 31
    assert rules.employed_days(first, last, date(2026, 10, 16), None) == 16
    assert rules.employed_days(first, last, date(2020, 1, 1), date(2026, 10, 10)) == 10
    assert rules.employed_days(first, last, date(2026, 11, 1), None) == 0


def test_payslip_lines_are_proportional_and_exact():
    structure = rules.check_lines(
        [
            {"code": "basic", "kind": "earning", "amount": "30000.00"},
            {"code": "HRA", "kind": "earning", "amount": "12000"},
            {"code": "PF", "kind": "deduction", "amount": "3600.00"},
        ]
    )
    assert structure[0]["code"] == "BASIC" and structure[0]["name"] == "BASIC"
    assert rules.payslip_lines(structure, 31, Decimal(31)) == structure
    lines = rules.payslip_lines(structure, 31, Decimal(28))
    assert [x["amount"] for x in lines] == ["27096.77", "10838.71", "3251.61"]
    assert rules.totals(lines) == (Decimal("37935.48"), Decimal("3251.61"), Decimal("34683.87"))
    half = rules.payslip_lines(structure, 30, Decimal("29.5"))
    assert half[0]["amount"] == "29500.00"


def test_pay_lines_are_checked():
    earning = {"code": "BASIC", "kind": "earning", "amount": "100.00"}
    for lines, code in (
        ([], "no_earnings"),
        ([{"code": "PF", "kind": "deduction", "amount": "1.00"}], "no_earnings"),
        ([earning, earning], "duplicate_line_code"),
        ([earning, {"code": "PF", "kind": "deduction", "amount": "100.01"}], "deductions_exceed_earnings"),
        ([{**earning, "amount": "1.001"}], "invalid_amount"),
        ([{**earning, "kind": "bonus"}], "invalid_line_kind"),
    ):
        with pytest.raises(RuleError) as err:
            rules.check_lines(lines)
        assert err.value.code == code
