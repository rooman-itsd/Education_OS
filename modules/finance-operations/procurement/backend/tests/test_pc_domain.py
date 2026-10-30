"""Pure rules: purchase method by value, order totals, invoice matching, quantities and masked bank accounts."""

from decimal import Decimal

import pytest
from eos_procurement.domain import rules
from eos_procurement.domain.rules import RuleError

D = Decimal


def test_purchase_method_follows_the_limits():
    assert rules.purchase_method(D("50000.00"), D("50000"), D("500000")) == "direct"
    assert rules.purchase_method(D("50000.01"), D("50000"), D("500000")) == "quotation"
    assert rules.purchase_method(D("500000.00"), D("50000"), D("500000")) == "quotation"
    assert rules.purchase_method(D("500000.01"), D("50000"), D("500000")) == "tender"


@pytest.mark.parametrize("direct,quotation", [(None, D("1")), (D("1"), None), (None, None), (D("10"), D("5"))])
def test_no_method_is_guessed_without_valid_limits(direct, quotation):
    with pytest.raises(RuleError) as e:
        rules.purchase_method(D("10"), direct, quotation)
    assert e.value.code == "purchase_limits_not_configured"


def test_a_stricter_method_is_allowed_a_looser_one_is_not():
    assert rules.method_allows("tender", "quotation") and rules.method_allows("quotation", "direct")
    assert not rules.method_allows("quotation", "tender")


def test_order_totals_round_each_line_to_the_paisa():
    items = [
        {"quantity": "3", "unit_price": "33.33", "tax_percent": "18"},  # 99.99 + 18.00
        {"quantity": "2.5", "unit_price": "10.00"},  # 25.00, no tax
    ]
    assert rules.order_totals(items) == (D("124.99"), D("18.00"), D("142.99"))
    with pytest.raises(RuleError):
        rules.order_totals([{"quantity": "1"}])


def test_accepted_value_and_tolerance():
    items = [{"quantity": "10", "unit_price": "100.00", "tax_percent": "18"}, {"quantity": "1", "unit_price": "50.00"}]
    assert rules.accepted_value(items, {0: D("4")}) == D("472.00")
    assert rules.accepted_value(items, {}) == D("0.00")
    assert rules.within_tolerance(D("472.00"), D("472.00"), D("0"))
    assert not rules.within_tolerance(D("472.01"), D("472.00"), D("0"))
    assert rules.within_tolerance(D("495.60"), D("472.00"), D("5"))


def test_quantities_and_money_are_exact():
    assert rules.parse_quantity("2.5") == D("2.500")
    for bad in ("0", "-1", "1.0001", "abc"):
        with pytest.raises(RuleError):
            rules.parse_quantity(bad)
    assert rules.parse_quantity("0", positive=False) == D("0.000")
    assert rules.number(D("4.000")) == 4 and rules.number(D("2.500")) == 2.5
    with pytest.raises(RuleError):
        rules.parse_money("1000000000000")


def test_only_the_last_four_digits_of_an_account_are_kept():
    assert rules.account_last4("1234 5678 9012") == "9012"
    for bad in ("12345", "ABCD123456", ""):
        with pytest.raises(RuleError):
            rules.account_last4(bad)
