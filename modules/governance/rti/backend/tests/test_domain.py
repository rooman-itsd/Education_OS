"""Dates, deadlines and rules of the domain: pure functions, no database."""

from datetime import UTC, date, datetime, timedelta

import pytest
from eos_rti.domain import deadlines as dl
from eos_rti.domain import requests as rules
from eos_rti.domain.dates import CALENDAR, WORKING, add_days, end_of_day, today_in_india
from eos_rti.domain.errors import DomainRuleError


def test_today_is_the_date_in_india_not_in_utc():
    # 19:00 UTC on the 5th is 00:30 on the 6th in India.
    assert today_in_india(datetime(2026, 11, 5, 19, 0, tzinfo=UTC)) == date(2026, 11, 6)
    assert today_in_india(datetime(2026, 11, 5, 18, 29, 59, tzinfo=UTC)) == date(2026, 11, 5)
    assert today_in_india(datetime(2026, 11, 5, 18, 30, tzinfo=UTC)) == date(2026, 11, 6)


def test_a_due_date_stops_being_met_at_the_end_of_the_day_in_india():
    assert end_of_day(date(2026, 12, 5)) == datetime(2026, 12, 5, 18, 29, 59, tzinfo=UTC)


@pytest.mark.parametrize(
    ("start", "n", "counting", "expected"),
    [
        (date(2026, 11, 5), 30, CALENDAR, date(2026, 12, 5)),
        (date(2026, 1, 31), 30, CALENDAR, date(2026, 3, 2)),  # across a short month
        (date(2028, 2, 1), 30, CALENDAR, date(2028, 3, 2)),  # across a leap day
        (date(2026, 11, 5), 1, CALENDAR, date(2026, 11, 6)),
        # Thursday 5 November 2026, working days: the day itself is day 0, weekends do not count.
        (date(2026, 11, 5), 1, WORKING, date(2026, 11, 6)),  # Friday
        (date(2026, 11, 5), 2, WORKING, date(2026, 11, 9)),  # Monday
        (date(2026, 11, 6), 1, WORKING, date(2026, 11, 9)),  # from a Friday
        (date(2026, 11, 7), 1, WORKING, date(2026, 11, 9)),  # from a Saturday
        (date(2026, 11, 8), 1, WORKING, date(2026, 11, 9)),  # from a Sunday
        (date(2026, 11, 5), 30, WORKING, date(2026, 12, 17)),  # six weeks
        (date(2026, 11, 5), 5, WORKING, date(2026, 11, 12)),  # a full week
    ],
)
def test_add_days(start, n, counting, expected):
    assert add_days(start, n, counting) == expected


def test_working_days_never_end_on_a_weekend():
    for offset in range(60):
        due = add_days(date(2026, 11, 1 + offset % 28), 1 + offset % 40, WORKING)
        assert due.weekday() < 5


def test_add_days_refuses_what_it_cannot_count():
    with pytest.raises(ValueError, match="negative"):
        add_days(date(2026, 1, 1), -1)
    with pytest.raises(ValueError, match="unknown"):
        add_days(date(2026, 1, 1), 1, "fortnights")


def test_no_setting_means_no_due_date_and_nothing_overdue():
    tl = dl.Timelines()
    assert dl.response_due_on(date(2026, 1, 1), tl) is None
    assert dl.appeal_due_on(date(2026, 1, 1), tl) is None
    assert dl.appeal_window_end(date(2026, 1, 1), tl) is None
    assert dl.current_due_on("assigned", date(2026, 1, 1), None, tl) is None
    assert not dl.is_overdue(None, date(2030, 1, 1))
    assert not dl.is_due_soon(None, date(2030, 1, 1), 7)


def test_a_request_due_today_is_due_soon_not_overdue():
    today, due = date(2026, 11, 5), date(2026, 11, 5)
    assert not dl.is_overdue(due, today)
    assert dl.is_due_soon(due, today, 7)
    assert dl.is_overdue(due, date(2026, 11, 6))
    assert not dl.is_due_soon(due, date(2026, 11, 6), 7)
    assert dl.is_due_soon(date(2026, 11, 12), today, 7)
    assert not dl.is_due_soon(date(2026, 11, 13), today, 7)


def test_the_deadline_a_request_waits_on_depends_on_its_status():
    tl = dl.Timelines(response_days=30, appeal_decide_days=10)
    received, filed = date(2026, 10, 1), date(2026, 11, 1)
    assert dl.current_due_on("received", received, None, tl) == date(2026, 10, 31)
    assert dl.current_due_on("assigned", received, None, tl) == date(2026, 10, 31)
    assert dl.current_due_on("appealed", received, filed, tl) == date(2026, 11, 11)
    for status in ("responded", "appeal_decided", "transferred", "closed"):
        assert dl.current_due_on(status, received, filed, tl) is None


def test_nearing_deadline_counts_everything_and_lists_the_soonest_ten():
    today = date(2026, 11, 5)
    items = [dl.OpenItem(f"id{n}", f"RTI-{n:06d}", "assigned", n, today + timedelta(days=n - 8)) for n in range(1, 15)]
    result = dl.nearing_deadline(items, 3, today)  # due dates from 7 days ago to 6 days ahead
    assert result.overdue == 7  # n=1..7 are before the 5th
    assert result.due_soon == 4  # the 5th, 6th, 7th and 8th
    assert [i.number for i in result.items][:3] == ["RTI-000001", "RTI-000002", "RTI-000003"]  # longest overdue first
    assert len(result.items) == dl.LIST_SIZE
    assert result.items[0].overdue and result.items[0].due_at == end_of_day(date(2026, 10, 29))


def test_moves_follow_the_status_diagram():
    assert rules.move("assign", "received") == "assigned"
    assert rules.move("assign", "assigned") == "assigned"
    assert rules.move("respond", "assigned") == "responded"
    assert rules.move("transfer", "received") == "transferred"
    assert rules.move("appeal", "responded") == "appealed"
    assert rules.move("decide", "appealed") == "appeal_decided"
    assert rules.move("close", "responded") == "closed"
    assert rules.move("close", "appeal_decided") == "closed"
    assert rules.move("refer", "assigned") == "assigned"  # a referral does not change the status
    assert rules.move("correct", "received") == "received"


@pytest.mark.parametrize(
    ("action", "status"),
    [
        ("assign", "responded"),
        ("respond", "received"),
        ("respond", "transferred"),
        ("transfer", "responded"),
        ("appeal", "assigned"),
        ("appeal", "closed"),
        ("decide", "responded"),
        ("close", "assigned"),
        ("close", "appealed"),
        ("close", "closed"),
        ("close", "transferred"),
        ("refer", "received"),
        ("correct", "responded"),
    ],
)
def test_any_other_move_is_a_conflict(action, status):
    with pytest.raises(DomainRuleError) as e:
        rules.move(action, status)
    assert (e.value.kind, e.value.code) == ("conflict", "invalid_status")


def test_every_status_that_is_not_final_has_a_way_out():
    final = {"closed", "transferred"}
    for status in rules.REQUEST_STATUSES:
        leaves = [a for a, (allowed, to, _) in rules.MOVES.items() if status in allowed and to not in (None, status)]
        assert bool(leaves) != (status in final), status


def test_grounds_are_required_when_the_information_is_withheld():
    rules.check_response("information_provided", None)
    for kind in ("partly_provided", "refused"):
        with pytest.raises(DomainRuleError) as e:
            rules.check_response(kind, "   ")
        assert (e.value.kind, e.value.code, e.value.field) == ("invalid", "grounds_required", "grounds")
        rules.check_response(kind, "Section 8(1)(j) applies.")


def test_dates_are_bounded_and_not_in_the_future():
    today = date(2026, 11, 5)
    rules.check_not_future(today, today, "x")
    for value in (date(2026, 11, 6), date(1899, 12, 31), date(2200, 1, 1)):
        with pytest.raises(DomainRuleError):
            rules.check_not_future(value, today, "x")
    with pytest.raises(DomainRuleError, match="before"):
        rules.check_not_before(date(2026, 1, 1), date(2026, 1, 2), "x", "the day")


def test_a_referral_question_must_not_repeat_the_applicant():
    applicant = {"name": "Asha Verma", "email": "asha.verma@example.org", "phone": "+91 98450 00000"}
    assert rules.question_repeats_applicant("What was the cut-off in 2025?", applicant) is None
    assert rules.question_repeats_applicant("Papers of ASHA VERMA please", applicant) == "name"
    assert rules.question_repeats_applicant("Write to asha.verma@example.org", applicant) == "email"
    assert rules.question_repeats_applicant("Call +91 98450 00000", applicant) == "phone"
    assert rules.question_repeats_applicant("Anything about Li?", {"name": "Li"}) is None  # too short to match


def test_how_a_request_closed():
    assert rules.closure_of("responded") == "responded"
    assert rules.closure_of("appeal_decided") == "appeal_decided"
