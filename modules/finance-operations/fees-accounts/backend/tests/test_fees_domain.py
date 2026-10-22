"""Pure fee rules: exact money, instalment splits, late fees, ageing and allocation."""

from datetime import date
from decimal import Decimal

import pytest
from eos_fees_accounts.domain import rules
from eos_fees_accounts.domain.rules import Instalment, LateFeeRule, RuleError

D = Decimal


def test_money_is_exact_two_places():
    assert rules.money("1500") == "1500.00"
    assert rules.parse_money("10.5") == D("10.50")
    for bad in ("0", "-1", "1.234", "abc", "NaN"):
        with pytest.raises(RuleError):
            rules.parse_money(bad)
    assert rules.parse_money("0", positive=False) == D("0.00")


def test_instalments_must_add_up_to_100():
    ok = [Instalment("T1", D(60), date(2026, 1, 1)), Instalment("T2", D(40), date(2026, 6, 1))]
    rules.check_instalments(ok)
    with pytest.raises(RuleError):
        rules.check_instalments([Instalment("T1", D(60), date(2026, 1, 1))])
    with pytest.raises(RuleError):
        rules.check_instalments([])


def test_split_item_never_loses_a_paisa():
    shares = rules.split_item(D("1000.00"), [D("33.33"), D("33.33"), D("33.34")])
    assert sum(shares) == D("1000.00")
    assert shares == [D("333.30"), D("333.30"), D("333.40")]
    odd = rules.split_item(D("100.01"), [D(50), D(50)])
    assert odd == [D("50.01"), D("50.00")] and sum(odd) == D("100.01")


def test_instalment_lines_by_position():
    items = [("tuition", D("30000.00")), ("library", D("10000.00"))]
    assert rules.instalment_lines(items, [D(60), D(40)], 1) == [("tuition", D("18000.00")), ("library", D("6000.00"))]
    assert rules.instalment_lines(items, [D(60), D(40)], 2) == [("tuition", D("12000.00")), ("library", D("4000.00"))]
    assert rules.instalment_lines(items, [D(100), D(0)], 2) == []
    with pytest.raises(RuleError):
        rules.instalment_lines(items, [D(60), D(40)], 3)


def test_late_fee_flat_per_day_grace_and_cap():
    due = date(2026, 10, 1)
    flat = LateFeeRule("flat", D("200.00"), grace_days=5)
    assert rules.late_fee(flat, due, date(2026, 10, 6)) == D("0.00")
    assert rules.late_fee(flat, due, date(2026, 10, 7)) == D("200.00")
    assert rules.late_fee(flat, due, date(2026, 12, 7)) == D("200.00")
    daily = LateFeeRule("per_day", D("10.00"), grace_days=0, cap=D("50.00"))
    assert rules.late_fee(daily, due, date(2026, 10, 3)) == D("20.00")
    assert rules.late_fee(daily, due, date(2026, 11, 3)) == D("50.00")
    assert rules.late_fee(None, due, date(2027, 1, 1)) == D("0.00")


def test_status_follows_balance():
    assert rules.invoice_status("issued", D("100"), D("0")) == "issued"
    assert rules.invoice_status("issued", D("40"), D("60")) == "partially_paid"
    assert rules.invoice_status("partially_paid", D("0"), D("100")) == "paid"
    assert rules.invoice_status("paid", D("50"), D("50")) == "partially_paid"
    assert rules.invoice_status("cancelled", D("0"), D("0")) == "cancelled"


def test_ageing_buckets():
    today = date(2026, 10, 22)
    assert rules.ageing_bucket(date(2026, 10, 22), today) == "not_due"
    assert rules.ageing_bucket(date(2026, 10, 21), today) == "0-30"
    assert rules.ageing_bucket(date(2026, 9, 1), today) == "31-60"
    assert rules.ageing_bucket(date(2026, 8, 1), today) == "61-90"
    assert rules.ageing_bucket(date(2026, 1, 1), today) == "90+"


def test_allocate_is_proportional_and_exact():
    shares = rules.allocate(D("100.00"), [D("1"), D("1"), D("1")])
    assert shares == [D("33.33"), D("33.33"), D("33.34")]
    assert rules.allocate(D("10.00"), []) == []


def test_concession_amount_or_percent():
    assert rules.concession_amount(D("1000"), D("250.00"), None) == D("250.00")
    assert rules.concession_amount(D("1000"), None, D("12.5")) == D("125.00")
    with pytest.raises(RuleError):
        rules.concession_amount(D("1000"), D("1"), D("1"))
    with pytest.raises(RuleError):
        rules.concession_amount(D("1000"), None, None)


def test_academic_year():
    assert rules.academic_year_of(date(2026, 10, 22), 6) == "2026-27"
    assert rules.academic_year_of(date(2027, 3, 1), 6) == "2026-27"
    months = rules.academic_year_months("2026-27", 6)
    assert months[0] == "2026-06" and months[-1] == "2027-05" and len(months) == 12
    with pytest.raises(RuleError):
        rules.academic_year_months("next year", 6)
