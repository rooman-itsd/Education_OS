"""Pure domain rules: usage window, weekly slots, periods and the hours arithmetic of utilisation."""

from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from eos_sports_facilities.domain import rules
from eos_sports_facilities.domain.rules import RuleViolationError, Slot

KOLKATA = ZoneInfo("Asia/Kolkata")


def t(hour: int, minute: int = 0, day: int = 26) -> datetime:
    return datetime(2026, 10, day, hour, minute, tzinfo=UTC)


def code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


def test_usage_window_ends_after_it_starts():
    rules.check_window(t(9), t(10))
    assert code(rules.check_window, t(10), t(10)) == "invalid_window"
    assert code(rules.check_window, t(10), t(9)) == "invalid_window"


def test_slots_close_after_they_open_and_do_not_overlap():
    ordered = rules.check_slots([Slot(1, "16:00", "21:00"), Slot(0, "06:00", "09:00"), Slot(1, "06:00", "09:00")])
    assert [(s.day_of_week, s.opens_at) for s in ordered] == [(0, "06:00"), (1, "06:00"), (1, "16:00")]
    assert code(rules.check_slots, [Slot(0, "09:00", "09:00")]) == "invalid_slot"
    assert code(rules.check_slots, [Slot(0, "21:00", "06:00")]) == "invalid_slot"
    assert code(rules.check_slots, [Slot(2, "06:00", "10:00"), Slot(2, "09:00", "12:00")]) == "overlapping_slots"
    rules.check_slots([Slot(2, "06:00", "10:00"), Slot(2, "10:00", "12:00")])  # touching is fine
    assert rules.check_slots([]) == []


def test_period_is_inclusive_and_at_most_366_days():
    rules.check_period(date(2026, 1, 1), date(2026, 1, 1))
    rules.check_period(date(2028, 1, 1), date(2028, 12, 31))  # a leap year is 366 days
    assert code(rules.check_period, date(2026, 1, 2), date(2026, 1, 1)) == "invalid_period"
    assert code(rules.check_period, date(2026, 1, 1), date(2027, 1, 2)) == "period_too_long"


def test_local_bounds_are_local_midnights():
    start, end = rules.local_bounds(date(2026, 10, 26), date(2026, 10, 26), KOLKATA)
    assert start == datetime(2026, 10, 25, 18, 30, tzinfo=UTC)
    assert end == start + timedelta(days=1)
    assert rules.local_bounds(None, None, KOLKATA) == (None, None)


def test_hours_open_from_weekly_slots_or_all_day():
    monday, sunday = date(2026, 10, 26), date(2026, 11, 1)
    assert rules.hours_open([], monday, sunday) == 7 * 24
    slots = [Slot(0, "06:00", "09:00"), Slot(0, "16:00", "21:30"), Slot(5, "07:00", "12:00")]
    assert rules.hours_open(slots, monday, sunday) == 3 + 5.5 + 5
    assert rules.hours_open(slots, date(2026, 10, 27), date(2026, 10, 30)) == 0  # Tuesday to Friday: closed


def test_hours_in_use_counts_overlaps_once_and_clips_to_the_period():
    start, end = t(0), t(0, day=27)
    windows = [(t(9), t(11)), (t(10), t(12)), (t(14), t(15)), (t(23), t(2, day=27))]
    assert rules.hours_in_use(windows, start, end) == 3 + 1 + 1
    assert rules.hours_in_use([], start, end) == 0
    assert rules.hours_in_use([(t(9), t(10))], t(10), t(11)) == 0
