"""The cron evaluator: fields, the day-of-month / day-of-week rule, timezones and daylight-saving changes."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from eos_scheduler.domain.cron import Cron, CronError


def utc(*args) -> datetime:
    return datetime(*args, tzinfo=UTC)


def test_daily_at_two_in_india_is_twenty_thirty_utc_the_day_before():
    c = Cron.parse("0 2 * * *")
    assert c.next_after(utc(2026, 10, 29, 12, 0), "Asia/Kolkata") == utc(2026, 10, 29, 20, 30)


def test_the_next_firing_is_strictly_after():
    c = Cron.parse("*/15 * * * *")
    assert c.next_after(utc(2026, 10, 29, 12, 0), "UTC") == utc(2026, 10, 29, 12, 15)
    assert c.next_after(utc(2026, 10, 29, 12, 7, 30), "UTC") == utc(2026, 10, 29, 12, 15)


def test_ranges_lists_and_steps():
    c = Cron.parse("5,35 9-17/4 * * 1-5")
    assert c.hours == {9, 13, 17} and c.minutes == {5, 35} and c.weekdays == {1, 2, 3, 4, 5}
    # Friday 30 Oct 2026, 17:35 -> next is Monday 2 Nov 09:05
    assert c.next_after(utc(2026, 10, 30, 17, 35), "UTC") == utc(2026, 11, 2, 9, 5)


def test_both_day_fields_restricted_means_either():
    c = Cron.parse("0 0 1 * 0")  # the 1st of the month, or any Sunday
    assert c.next_after(utc(2026, 10, 29), "UTC") == utc(2026, 11, 1)  # a Sunday and the 1st
    assert c.next_after(utc(2026, 11, 1), "UTC") == utc(2026, 11, 8)  # the next Sunday


def test_seven_is_sunday_and_months_skip_ahead():
    assert Cron.parse("0 0 * * 7").weekdays == {0}
    assert Cron.parse("0 0 29 2 *").next_after(utc(2026, 3, 1), "UTC") == utc(2028, 2, 29)


def test_a_time_skipped_by_spring_forward_fires_at_the_first_real_minute_after():
    # New York, 8 Mar 2026: 02:00 jumps to 03:00. 02:30 never happens on that day.
    fired = Cron.parse("30 2 * * *").next_after(utc(2026, 3, 8, 5, 0), "America/New_York")
    assert fired == utc(2026, 3, 8, 7, 30)  # 03:30 EDT is the first wall time at or after 02:30


def test_a_time_repeated_by_fall_back_fires_once():
    # New York, 1 Nov 2026: 01:00-02:00 happens twice. 01:30 fires at the first of the two only.
    c = Cron.parse("30 1 * * *")
    first = c.next_after(utc(2026, 11, 1, 4, 0), "America/New_York")
    assert first == utc(2026, 11, 1, 5, 30)
    assert c.next_after(first, "America/New_York") == utc(2026, 11, 2, 6, 30)


@pytest.mark.parametrize(
    "expression",
    ["* * * *", "60 * * * *", "* 24 * * *", "* * 0 * *", "* * * 13 *", "*/0 * * * *", "MON * * * *", "5-1 * * * *"],
)
def test_a_bad_expression_is_refused(expression):
    with pytest.raises(CronError):
        Cron.parse(expression)


def test_an_unknown_timezone_is_refused():
    with pytest.raises(CronError, match="timezone"):
        Cron.parse("0 0 * * *").next_after(utc(2026, 1, 1), "Mars/Olympus")


def test_a_date_that_never_comes_is_refused():
    with pytest.raises(CronError, match="never fires"):
        Cron.parse("0 0 31 2 *").next_after(utc(2026, 1, 1), "UTC")
