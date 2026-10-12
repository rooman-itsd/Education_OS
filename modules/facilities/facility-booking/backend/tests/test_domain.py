"""Unit tests of the pure booking rules (domain layer)."""

from datetime import UTC, date, datetime, timedelta

import pytest
from eos_facility_booking.domain.rules import (
    OpeningHours,
    Rules,
    RuleViolationError,
    Window,
    check_window,
    closed_windows,
    effective_rules,
    expand_recurrence,
    find_conflicts,
    full_windows,
    subtract,
)

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)  # Monday


def w(start_h: float, end_h: float, day: int = 12) -> Window:
    base = datetime(2026, 10, day, tzinfo=UTC)
    return Window(base + timedelta(hours=start_h), base + timedelta(hours=end_h))


def check(window: Window, rules: Rules = Rules(), opening=(), blackouts=()) -> None:
    check_window(window, rules, now=NOW, opening=list(opening), blackouts=list(blackouts), tz=UTC)


def test_effective_rules_later_layers_win_and_nulls_are_ignored():
    rules = effective_rules(
        Rules(slot_minutes=30),
        {"slot_minutes": 15, "buffer_minutes": 5},
        {"slot_minutes": None, "requires_approval": True, "bookable_role_ids": ["a"]},
    )
    assert rules.slot_minutes == 15
    assert rules.buffer_minutes == 5
    assert rules.requires_approval is True
    assert rules.bookable_role_ids == ("a",)


@pytest.mark.parametrize(
    ("window", "rules", "code"),
    [
        (w(10, 9), Rules(), "invalid_window"),
        (w(6, 7), Rules(), "in_the_past"),
        (w(9, 9.5), Rules(min_duration_minutes=60), "too_short"),
        (w(9, 12), Rules(max_duration_minutes=120), "too_long"),
        (w(9, 10, day=30), Rules(max_days_ahead=7), "too_far_ahead"),
        (w(9.25, 10), Rules(slot_minutes=30), "misaligned_slot"),
    ],
)
def test_check_window_rejects(window, rules, code):
    with pytest.raises(RuleViolationError) as e:
        check(window, rules)
    assert e.value.code == code


def test_opening_hours_and_blackouts():
    monday_9_to_17 = [OpeningHours(1, "09:00", "17:00")]
    check(w(9, 10), opening=monday_9_to_17)
    with pytest.raises(RuleViolationError, match="closed") as e:
        check(w(16, 18), opening=monday_9_to_17)
    assert e.value.code == "outside_opening_hours"
    with pytest.raises(RuleViolationError) as e:
        check(w(9, 10, day=13), opening=monday_9_to_17)  # Tuesday has no hours
    assert e.value.code == "outside_opening_hours"
    with pytest.raises(RuleViolationError) as e:
        check(w(9, 10), blackouts=[w(9.5, 11)])
    assert e.value.code == "in_blackout"


def test_conflicts_respect_buffer_and_concurrency():
    existing = [w(9, 10)]
    assert find_conflicts(w(10, 11), existing, buffer_minutes=0, max_concurrent=1) == []
    assert find_conflicts(w(10, 11), existing, buffer_minutes=15, max_concurrent=1) == existing
    assert find_conflicts(w(9, 10), existing, buffer_minutes=0, max_concurrent=2) == []
    assert find_conflicts(w(9, 10), [w(9, 10), w(9.5, 10)], buffer_minutes=0, max_concurrent=2) != []


def test_weekly_recurrence_by_count_and_until():
    first = w(9, 10)  # Monday
    by_count = expand_recurrence(first, frequency="weekly", weekdays=[1, 3], count=4, limit=52, tz=UTC)
    assert [o.start.date() for o in by_count] == [
        date(2026, 10, 12),
        date(2026, 10, 14),
        date(2026, 10, 19),
        date(2026, 10, 21),
    ]
    by_until = expand_recurrence(first, frequency="daily", interval=2, until=date(2026, 10, 16), limit=52, tz=UTC)
    assert [o.start.day for o in by_until] == [12, 14, 16]
    assert all(o.minutes == 60 for o in by_until)


def test_recurrence_limits():
    with pytest.raises(RuleViolationError) as e:
        expand_recurrence(w(9, 10), frequency="daily", count=60, limit=52, tz=UTC)
    assert e.value.code == "too_many_occurrences"
    with pytest.raises(RuleViolationError):
        expand_recurrence(w(9, 10), frequency="daily", limit=52, tz=UTC)


def test_availability_helpers():
    span = w(0, 24)
    closed = closed_windows(span, [OpeningHours(1, "09:00", "17:00")], UTC)
    assert closed == [w(0, 9), w(17, 24)]
    assert full_windows([w(9, 11), w(10, 12)], 2) == [w(10, 11)]
    assert subtract(w(9, 17), [w(10, 11), w(12, 13)]) == [w(9, 10), w(11, 12), w(13, 17)]
