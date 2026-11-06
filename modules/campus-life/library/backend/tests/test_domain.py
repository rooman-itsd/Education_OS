"""Domain rules, without the database or HTTP."""

from datetime import date
from decimal import Decimal

import pytest
from eos_library.domain import rules
from eos_library.domain.rules import Policy, RefusedError, RuleViolationError

POLICY = Policy(
    max_loans=2, loan_days=14, max_renewals=1, fine_per_day=Decimal("2.00"), max_unpaid_fines=Decimal("10.00")
)


def issue(**over):
    args = dict(
        is_member=True,
        blocked=False,
        policy=POLICY,
        active_loans=0,
        unpaid_fines=Decimal("0"),
        copy_status="available",
        held_for=None,
        person_id="p1",
    )
    args.update(over)
    rules.check_issue(**args)


def test_money_is_exact():
    assert rules.parse_money("25") == Decimal("25.00")
    assert rules.money_str(Decimal("0.1") + Decimal("0.2")) == "0.30"
    for bad in ("-1", "1.234", "abc", "1e3", ""):
        with pytest.raises(RuleViolationError):
            rules.parse_money(bad)


def test_overdue_fine_counts_whole_days_after_due():
    due = date(2026, 11, 12)
    assert rules.days_late(due, date(2026, 11, 12)) == 0
    assert rules.days_late(due, date(2026, 11, 15)) == 3
    assert rules.overdue_fine(due, date(2026, 11, 15), Decimal("2.00")) == Decimal("6.00")
    assert rules.overdue_fine(due, date(2026, 11, 1), Decimal("2.00")) == Decimal("0.00")


@pytest.mark.parametrize(
    ("over", "code"),
    [
        ({"is_member": False}, rules.NOT_A_MEMBER),
        ({"blocked": True}, rules.MEMBER_BLOCKED),
        ({"policy": None}, rules.LOAN_LIMIT),
        ({"active_loans": 2}, rules.LOAN_LIMIT),
        ({"unpaid_fines": Decimal("10.01")}, rules.UNPAID_FINES),
        ({"copy_status": "on-loan"}, rules.COPY_UNAVAILABLE),
        ({"copy_status": "withdrawn"}, rules.COPY_UNAVAILABLE),
        ({"copy_status": "on-hold", "held_for": "someone-else"}, rules.HELD_FOR_OTHER),
    ],
)
def test_issue_refusals(over, code):
    with pytest.raises(RefusedError) as e:
        issue(**over)
    assert e.value.code == code


def test_issue_allowed():
    issue()
    issue(unpaid_fines=Decimal("10.00"))  # exactly at the limit is allowed
    issue(copy_status="on-hold", held_for="p1")  # the copy held for this member


def test_renew_rules():
    rules.check_renew(renewals=0, policy=POLICY, someone_waiting=False)
    with pytest.raises(RefusedError) as e:
        rules.check_renew(renewals=1, policy=POLICY, someone_waiting=False)
    assert e.value.code == rules.NO_RENEWALS_LEFT
    with pytest.raises(RefusedError) as e:
        rules.check_renew(renewals=0, policy=POLICY, someone_waiting=True)
    assert e.value.code == rules.TITLE_RESERVED
    assert rules.renewals_left(1, POLICY) == 0 and rules.renewals_left(0, None) == 0


def test_holds():
    assert rules.hold_expiry(date(2026, 10, 29), 3) == date(2026, 11, 1)
    assert rules.hold_expired(date(2026, 11, 1), date(2026, 11, 2))
    assert not rules.hold_expired(date(2026, 11, 1), date(2026, 11, 1))
    assert not rules.hold_expired(None, date(2026, 11, 2))
