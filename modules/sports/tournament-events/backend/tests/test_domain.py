"""Domain rules, without HTTP or a database."""

from datetime import UTC, date, datetime, timedelta

import pytest
from eos_tournament_events.domain import rules
from eos_tournament_events.domain.rules import RuleViolationError

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
START, END = date(2026, 11, 10), date(2026, 11, 12)


def _code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


@pytest.mark.parametrize(
    ("stored", "on", "expected"),
    [
        ("draft", date(2026, 11, 11), "draft"),
        ("cancelled", date(2026, 11, 11), "cancelled"),
        ("published", date(2026, 11, 9), "published"),
        ("published", START, "ongoing"),
        ("published", END, "ongoing"),
        ("published", date(2026, 11, 13), "completed"),
    ],
)
def test_effective_status_follows_the_dates_of_a_published_tournament(stored, on, expected):
    assert rules.effective_status(stored, START, END, on) == expected


def test_tournament_dates():
    rules.check_tournament_dates(START, START, START)
    assert _code(rules.check_tournament_dates, END, START, None) == "end_before_start"
    assert _code(rules.check_tournament_dates, START, END, date(2026, 11, 13)) == "registration_after_end"


def test_tournament_state_machine():
    rules.check_publish("draft")
    for status in ("published", "ongoing", "completed", "cancelled"):
        assert _code(rules.check_publish, status) == "not_draft"
    for status in ("draft", "published", "ongoing"):
        rules.check_cancel(status)
    assert _code(rules.check_cancel, "cancelled") == "already_cancelled"
    assert _code(rules.check_cancel, "completed") == "tournament_completed"
    assert _code(rules.check_editable, "completed") == "tournament_closed"
    assert _code(rules.check_schedulable, "draft") == "tournament_not_published"
    assert _code(rules.check_schedulable, "cancelled") == "tournament_closed"
    rules.check_schedulable("completed")  # late fixtures of a finished tournament can still be recorded


def test_entries_open_after_publishing_until_the_deadline():
    rules.check_entries_open("published", date(2026, 11, 5), date(2026, 11, 5))
    rules.check_entries_open("ongoing", None, date(2026, 11, 11))
    assert _code(rules.check_entries_open, "draft", None, NOW.date()) == "entries_not_open"
    assert _code(rules.check_entries_open, "completed", None, NOW.date()) == "entries_not_open"
    assert _code(rules.check_entries_open, "published", date(2026, 11, 5), date(2026, 11, 6)) == "registration_closed"


def test_entry_rules():
    assert _code(rules.check_athletes, []) == "no_athletes"
    assert _code(rules.check_athletes, ["a", "a"]) == "duplicate_athlete"
    assert _code(rules.check_new_entry_status, "withdrawn") == "invalid_status"
    rules.check_entry_transition("pending", "confirmed")
    rules.check_entry_transition("confirmed", "withdrawn")
    rules.check_entry_transition("withdrawn", "withdrawn")
    assert _code(rules.check_entry_transition, "confirmed", "pending") == "invalid_transition"
    assert _code(rules.check_entry_transition, "withdrawn", "confirmed") == "invalid_transition"
    assert rules.already_entered(["a", "b"], [["c"], ["b"]]) == "b"
    assert rules.already_entered(["a"], [["c"]]) is None


@pytest.mark.parametrize(
    ("current", "new"),
    [
        ("scheduled", "in_progress"),
        ("scheduled", "postponed"),
        ("scheduled", "cancelled"),
        ("postponed", "scheduled"),
        ("in_progress", "postponed"),
        ("in_progress", "cancelled"),
    ],
)
def test_fixture_moves(current, new):
    rules.check_fixture_transition(current, new)


@pytest.mark.parametrize(
    ("current", "new", "code"),
    [
        ("scheduled", "completed", "record_result"),
        ("postponed", "in_progress", "invalid_transition"),
        ("in_progress", "scheduled", "invalid_transition"),
        ("cancelled", "scheduled", "invalid_transition"),
        ("completed", "in_progress", "invalid_transition"),
    ],
)
def test_fixture_refused_moves(current, new, code):
    assert _code(rules.check_fixture_transition, current, new) == code


def test_fixture_rules():
    assert _code(rules.check_new_fixture_status, "completed") == "invalid_status"
    assert _code(rules.check_fixture_entries, ["a", "a"]) == "duplicate_entry"
    assert _code(rules.check_fixture_editable, "completed") == "fixture_closed"
    rules.check_within_dates(START, START, END)
    assert _code(rules.check_within_dates, date(2026, 11, 13), START, END) == "outside_tournament_dates"


def test_results_only_for_started_fixtures_in_the_right_state():
    rules.check_result_allowed("scheduled", NOW, NOW)
    rules.check_result_allowed("in_progress", NOW - timedelta(hours=1), NOW)
    rules.check_result_allowed("completed", NOW - timedelta(hours=1), NOW)  # a correction
    assert _code(rules.check_result_allowed, "postponed", NOW, NOW) == "fixture_not_playable"
    assert _code(rules.check_result_allowed, "cancelled", NOW, NOW) == "fixture_not_playable"
    assert _code(rules.check_result_allowed, "scheduled", NOW + timedelta(minutes=1), NOW) == "fixture_not_started"


@pytest.mark.parametrize(
    ("placings", "code"),
    [
        ([], "no_placings"),
        ([{"entry_id": "x"}], "entry_not_in_fixture"),
        ([{"entry_id": "a"}, {"entry_id": "a"}], "duplicate_placing"),
        ([{"entry_id": "a", "position": 0}], "invalid_position"),
        ([{"entry_id": "a", "mark": float("nan")}], "invalid_mark"),
    ],
)
def test_placings(placings, code):
    assert _code(rules.check_placings, placings, ["a", "b"]) == code


def test_placings_may_tie():
    rules.check_placings([{"entry_id": "a", "position": 1}, {"entry_id": "b", "position": 1}], ["a", "b"])


def test_travel():
    rules.check_travel(NOW, NOW, 0)
    assert _code(rules.check_travel, NOW, NOW - timedelta(hours=1), None) == "return_before_departure"
    assert _code(rules.check_travel, None, None, -1) == "invalid_count"


def test_the_institution_timezone_resolves_without_a_time_zone_database():
    from eos_tournament_events.infrastructure.config import ModuleSettings

    assert ModuleSettings("Asia/Kolkata").tz.utcoffset(NOW) == timedelta(hours=5, minutes=30)
    assert ModuleSettings("UTC").tz.utcoffset(NOW) == timedelta(0)
    with pytest.raises(Exception):  # noqa: B017 - ZoneInfoNotFoundError, or ValueError for a malformed key
        _ = ModuleSettings("Nowhere/Atlantis").tz
