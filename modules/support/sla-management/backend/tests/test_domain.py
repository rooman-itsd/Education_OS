"""Domain rules without a database: business time, calendar checks, policy rules and clock moves."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta

import pytest
from eos_sla_management.domain import business_time as bt
from eos_sla_management.domain import clocks, policies
from eos_sla_management.domain.errors import DomainRuleError

OFFICE = [{"weekday": d, "start": "09:00", "end": "17:00"} for d in range(1, 6)]
MON = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)  # a Monday


def utc(day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(2026, 11, day, hour, minute, tzinfo=UTC)


def office(holidays=(), tz="UTC", hours=OFFICE) -> bt.BusinessCalendar:
    return bt.build(tz, False, hours, [{"date": d, "name": "Holiday"} for d in holidays])


# ---------------------------------------------------------------- business time


def test_the_monday_is_a_monday():
    assert MON.isoweekday() == 1


def test_shift_counts_only_working_hours():
    cal = office()
    assert bt.shift(cal, MON, 60) == utc(2, 10)
    assert bt.shift(cal, utc(2, 16, 30), 60) == utc(3, 9, 30)  # 30 minutes Monday, 30 Tuesday
    assert bt.shift(cal, utc(6, 16), 120) == utc(9, 10)  # Friday 16:00 + 2h -> Monday 10:00
    assert bt.shift(cal, utc(2, 7), 1) == utc(2, 9, 1)  # before opening counts from opening
    assert bt.shift(cal, utc(2, 9), 8 * 60) == utc(2, 17)  # exactly the day
    assert bt.shift(cal, MON, 0) == MON


def test_shift_backwards_and_between():
    cal = office()
    assert bt.shift(cal, utc(3, 9, 30), -60) == utc(2, 16, 30)
    assert bt.between(cal, utc(2, 16), utc(3, 10)) == 120
    assert bt.between(cal, utc(3, 10), utc(2, 16)) == 0
    assert bt.between(cal, utc(7, 0), utc(9, 0)) == 0  # weekend
    assert bt.between(cal, utc(2, 9), utc(2, 9, 0) + timedelta(seconds=59)) == 0  # whole minutes


def test_holidays_and_split_days_are_skipped():
    cal = office(holidays=[date(2026, 11, 3)])
    assert bt.shift(cal, utc(2, 16, 30), 60) == utc(4, 9, 30)
    split = office(
        hours=[{"weekday": 1, "start": "09:00", "end": "13:00"}, {"weekday": 1, "start": "14:00", "end": "18:00"}]
    )
    assert bt.shift(split, utc(2, 12), 120) == utc(2, 15)
    assert bt.between(split, utc(2, 9), utc(2, 18)) == 8 * 60


def test_time_zone_hours_are_local():
    cal = office(tz="Asia/Kolkata")  # UTC+05:30: 09:00 local is 03:30 UTC
    assert bt.shift(cal, utc(2, 0), 60) == utc(2, 4, 30)
    assert bt.between(cal, utc(2, 0), utc(3, 0)) == 8 * 60


def test_daylight_saving_change_counts_real_minutes():
    try:
        bt.zone("Europe/London")
    except DomainRuleError:
        pytest.skip("the host has no time-zone database")
    every_hour = [{"weekday": d, "start": "00:00", "end": "24:00"} for d in range(1, 8)]
    cal = office(tz="Europe/London", hours=every_hour)
    # Sunday 25 October 2026: clocks go back at 02:00 BST, so the local day has 25 hours.
    start = datetime(2026, 10, 24, 23, 0, tzinfo=UTC)  # 00:00 BST on the 25th
    end = datetime(2026, 10, 26, 0, 0, tzinfo=UTC)  # 00:00 GMT on the 26th
    assert bt.between(cal, start, end) == 25 * 60
    assert bt.shift(cal, start, 25 * 60) == end


def test_always_open_counts_every_minute():
    cal = bt.build("UTC", True, [], [{"date": date(2026, 11, 2), "name": "Ignored"}])
    assert bt.shift(cal, MON, 90) == MON + timedelta(minutes=90)
    assert bt.between(cal, MON, MON + timedelta(days=1)) == 1440


def test_a_target_beyond_the_horizon_is_unreachable():
    sparse = office(hours=[{"weekday": 1, "start": "09:00", "end": "09:01"}])
    assert bt.shift(sparse, MON, bt.MAX_TARGET_MINUTES) is None
    assert not bt.reachable(sparse, MON, bt.MAX_TARGET_MINUTES)
    assert bt.reachable(office(), MON, bt.MAX_TARGET_MINUTES)
    assert bt.shift(sparse, MON, -bt.MAX_TARGET_MINUTES) is None
    always = bt.build("UTC", True, [], [])
    assert bt.reachable(always, MON, bt.MAX_TARGET_MINUTES)


@pytest.mark.parametrize(
    ("time_zone", "always_open", "hours", "holidays", "code"),
    [
        ("Mars/Olympus", False, OFFICE, [], "unknown_time_zone"),
        ("../../etc/passwd", False, OFFICE, [], "unknown_time_zone"),
        ("x" * 65, False, OFFICE, [], "unknown_time_zone"),
        ("UTC", False, [], [], "working_hours_required"),
        ("UTC", False, [{"weekday": 1, "start": "10:00", "end": "09:00"}], [], "end_before_start"),
        ("UTC", False, [{"weekday": 1, "start": "10:00", "end": "10:00"}], [], "end_before_start"),
        ("UTC", False, [{"weekday": 1, "start": "10:00", "end": "24:30"}], [], "invalid_time"),
        (
            "UTC",
            False,
            [{"weekday": 1, "start": "09:00", "end": "13:00"}, {"weekday": 1, "start": "12:00", "end": "18:00"}],
            [],
            "overlapping_hours",
        ),
        ("UTC", True, [], [{"date": date(1, 1, 1), "name": "x"}], "invalid_holiday"),
        ("UTC", True, [], [{"date": date(9999, 12, 31), "name": "x"}], "invalid_holiday"),
    ],
)
def test_bad_calendars_are_refused(time_zone, always_open, hours, holidays, code):
    with pytest.raises(DomainRuleError) as err:
        bt.check_calendar(time_zone, always_open, hours, holidays)
    assert (err.value.code, err.value.kind) == (code, "invalid")


def test_good_calendars_pass():
    bt.check_calendar("UTC", False, OFFICE, [{"date": date(2026, 12, 25), "name": "Christmas"}])
    bt.check_calendar("UTC", True, [], [])
    adjacent = [{"weekday": 1, "start": "09:00", "end": "13:00"}, {"weekday": 1, "start": "13:00", "end": "24:00"}]
    bt.check_calendar("Etc/UTC", False, adjacent, [])


# ---------------------------------------------------------------- policies


def test_targets_and_escalation_levels():
    policies.check_targets(60, 60)
    with pytest.raises(DomainRuleError) as err:
        policies.check_targets(120, 60)
    assert (err.value.code, err.value.field) == ("resolution_before_response", "resolution_target_minutes")
    levels = [{"level": 1, "after_breach_minutes": 0}, {"level": 2, "after_breach_minutes": 30}]
    policies.check_escalation_levels(levels, 3)
    for bad, max_levels, code in [
        (levels, 1, "too_many_escalation_levels"),
        ([{"level": 2, "after_breach_minutes": 0}], 3, "escalation_levels_out_of_order"),
        (list(reversed(levels)), 3, "escalation_levels_out_of_order"),
        ([{"level": 1, "after_breach_minutes": 30}, {"level": 2, "after_breach_minutes": 0}], 3, None),
    ]:
        with pytest.raises(DomainRuleError) as err:
            policies.check_escalation_levels(bad, max_levels)
        assert err.value.code == (code or "escalation_times_out_of_order")


@dataclass
class P:
    name: str
    priority: str
    category_id: str | None
    active: bool = True


def test_the_most_specific_active_policy_applies():
    every = P("every", "high", None)
    specific = P("specific", "high", "c1")
    retired = P("retired", "high", "c2", active=False)
    found = [every, specific, retired, P("low", "low", "c1")]
    assert policies.choose(found, "high", "c1") is specific
    assert policies.choose(found, "high", "c2") is every
    assert policies.choose(found, "high", None) is every
    assert policies.choose(found, "urgent", "c1") is None
    assert policies.choose([specific], "high", "c3") is None
    assert policies.category_key(None) == "*"


# ---------------------------------------------------------------- clocks


def test_clock_moves():
    assert clocks.can("pause", "running", "response")
    assert not clocks.can("pause", "paused", "response")
    assert clocks.can("resume", "paused", "resolution")
    assert clocks.can("reopen", "stopped", "resolution")
    assert not clocks.can("reopen", "stopped", "response")
    assert clocks.can("stop", "paused", "response")
    assert not clocks.can("stop", "cancelled", "response")
    assert clocks.can("cancel", "paused", "resolution")
    assert not clocks.can("cancel", "stopped", "resolution")
    assert clocks.target_of("cancel") == "cancelled"


def test_warning_minutes_round_up():
    assert clocks.warning_minutes(60, 50) == 30
    assert clocks.warning_minutes(7, 75) == 6
    assert clocks.warning_minutes(1, 1) == 1
    assert clocks.outcome(True) == "breached" and clocks.outcome(False) == "met"


def test_escalation_recipients():
    levels = [
        {"level": 1, "after_breach_minutes": 0, "notify_assignee": True, "notify_person_ids": ["lead", "agent"]},
        {"level": 2, "after_breach_minutes": 5, "notify_assignee": False, "notify_person_ids": ["head"]},
    ]
    assert clocks.recipients(levels, 1, "agent") == ["agent", "lead"]
    assert clocks.recipients(levels, 1, None) == ["lead", "agent"]
    assert clocks.recipients(levels, 2, "agent") == ["head"]
    assert clocks.recipients(levels, 3, "agent") == []
    assert clocks.next_level(levels, 1)["level"] == 2
    assert clocks.next_level(levels, 2) is None


def test_error_kinds_are_checked():
    with pytest.raises(ValueError):
        DomainRuleError("x", "y", kind="bad")
