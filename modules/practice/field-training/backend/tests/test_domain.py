"""Domain rules (domain/rules.py) without HTTP or database."""

from datetime import UTC, date, datetime

import pytest
from eos_field_training.application import service
from eos_field_training.domain import rules
from eos_field_training.domain.rules import RuleViolationError


def code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


def test_transitions():
    assert rules.transition(rules.PLACEMENT_TRANSITIONS, "approve", "requested") == "assigned"
    assert rules.transition(rules.PLACEMENT_TRANSITIONS, "withdraw", "active") == "withdrawn"
    assert rules.transition(rules.OPENING_TRANSITIONS, "cancel", "closed") == "cancelled"
    assert rules.transition(rules.LOG_TRANSITIONS, "edit", "returned") == "submitted"
    assert code(rules.transition, rules.PLACEMENT_TRANSITIONS, "complete", "assigned") == "invalid_status"
    assert code(rules.transition, rules.PLACEMENT_TRANSITIONS, "withdraw", "completed") == "invalid_status"
    assert code(rules.transition, rules.OPENING_TRANSITIONS, "publish", "open") == "invalid_status"
    assert code(rules.transition, rules.LOG_TRANSITIONS, "edit", "verified") == "invalid_status"


def test_hours_in_quarter_steps():
    assert rules.to_minutes(0.25) == 15
    assert rules.to_minutes(7.75) == 465
    assert rules.to_minutes(0) == 0
    assert rules.to_hours(465) == 7.75
    assert rules.to_hours(None) == 0
    assert code(rules.to_minutes, 0.1) == "invalid_hours"
    assert code(rules.to_minutes, -1) == "invalid_hours"


def test_day_total_at_most_24_hours():
    rules.check_day_total(20 * 60, 4 * 60)
    assert code(rules.check_day_total, 20 * 60, 4 * 60 + 15) == "day_over_24_hours"


def test_periods_and_seats():
    d = date
    rules.check_within(d(2026, 11, 5), d(2026, 11, 30), d(2026, 11, 1), d(2026, 12, 31))
    assert code(rules.check_within, d(2026, 10, 31), d(2026, 11, 30), d(2026, 11, 1), d(2026, 12, 31)) == (
        "invalid_dates"
    )
    assert code(rules.check_period, d(2026, 11, 2), d(2026, 11, 1)) == "invalid_dates"
    assert rules.periods_overlap(d(2026, 11, 1), d(2026, 11, 30), d(2026, 11, 30), d(2026, 12, 5))
    assert not rules.periods_overlap(d(2026, 11, 1), d(2026, 11, 29), d(2026, 11, 30), d(2026, 12, 5))
    rules.check_seat(2, 1)
    assert code(rules.check_seat, 2, 2) == "no_seats"
    assert code(rules.check_seats_not_below_filled, 1, 2) == "seats_below_filled"
    assert rules.seats_left(2, 5) == 0


def test_log_date_window():
    d = date
    rules.check_log_date(d(2026, 11, 3), d(2026, 11, 2), None, d(2026, 11, 30), d(2026, 11, 3))
    assert code(rules.check_log_date, d(2026, 11, 1), d(2026, 11, 2), None, d(2026, 11, 30), d(2026, 11, 3)) == (
        "date_outside_placement"
    )
    assert code(rules.check_log_date, d(2026, 11, 4), d(2026, 11, 2), None, d(2026, 11, 30), d(2026, 11, 3)) == (
        "date_in_future"
    )
    # Started early: the window opens on the day it started.
    rules.check_log_date(d(2026, 11, 3), d(2026, 11, 10), d(2026, 11, 3), d(2026, 11, 30), d(2026, 11, 3))


def test_completion_refusals_in_contract_order():
    assert rules.completion_refusal("assigned", True, 0, 0, False, None)[0] == "not-active"
    assert rules.completion_refusal("active", False, 600, 600, False, None)[0] == "no-final-assessment"
    assert rules.completion_refusal("active", True, 540, 600, False, None)[0] == "hours-short"
    assert rules.completion_refusal("active", True, 540, 600, True, " ")[0] == "reason-required"
    assert rules.completion_refusal("active", True, 540, 600, True, "Illness, agreed") is None
    assert rules.completion_refusal("active", True, 600, 600, False, None) is None


def test_final_assessment_due_and_urgency():
    today = date(2026, 11, 3)
    assert rules.final_assessment_due(date(2026, 11, 10), today, False)
    assert not rules.final_assessment_due(date(2026, 11, 11), today, False)
    assert rules.final_assessment_due(date(2026, 10, 1), today, False)
    assert not rules.final_assessment_due(date(2026, 11, 5), today, True)
    keys = [rules.urgency(False, 5, date(2026, 11, 20)), rules.urgency(True, 0, date(2026, 11, 9))]
    assert sorted(keys)[0] == keys[1]


def test_my_placement_order():
    d = date
    rows = [
        ("completed", d(2026, 1, 1)),
        ("requested", d(2026, 12, 1)),
        ("assigned", d(2027, 1, 1)),
        ("active", d(2026, 11, 2)),
        ("assigned", d(2026, 12, 1)),
        ("withdrawn", d(2026, 6, 1)),
    ]
    rows.sort(key=lambda r: rules.my_placement_rank(*r))
    assert [r[0] for r in rows] == ["active", "assigned", "assigned", "requested", "withdrawn", "completed"]
    assert rows[1][1] == d(2026, 12, 1)


def test_business_date_is_asia_kolkata(monkeypatch):
    # 20:00 UTC on 3 November is already 01:30 on 4 November in India.
    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 11, 3, 20, 0, tzinfo=UTC))
    assert service.today() == date(2026, 11, 4)
    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 11, 3, 18, 29, tzinfo=UTC))
    assert service.today() == date(2026, 11, 3)
