"""Domain rules, without HTTP or a database."""

from datetime import UTC, date, datetime, timedelta

import pytest
from eos_training_video_analysis.domain import rules
from eos_training_video_analysis.domain.rules import RuleViolationError

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)


def _refused(code: str, fn, *args) -> None:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    assert e.value.code == code


def test_plan_period():
    rules.check_plan_period(date(2026, 10, 1), date(2026, 10, 1))
    _refused("invalid_period", rules.check_plan_period, date(2026, 10, 2), date(2026, 10, 1))


@pytest.mark.parametrize(
    ("current", "new"),
    [
        ("draft", "active"),
        ("draft", "archived"),
        ("active", "completed"),
        ("active", "archived"),
        ("completed", "archived"),
    ],
)
def test_plan_transitions_allowed(current, new):
    rules.check_plan_transition(current, new)
    rules.check_plan_transition(current, current)  # no move is not a transition


@pytest.mark.parametrize(
    ("current", "new"),
    [("active", "draft"), ("completed", "active"), ("archived", "active"), ("draft", "completed")],
)
def test_plan_transitions_refused(current, new):
    _refused("invalid_transition", rules.check_plan_transition, current, new)


def test_archived_plan_is_read_only_and_closed_plans_take_no_sessions():
    _refused("plan_archived", rules.check_plan_editable, "archived")
    rules.check_plan_editable("completed")
    for status in ("completed", "archived"):
        _refused("plan_closed", rules.check_plan_open, status)
    rules.check_plan_open("draft")


@pytest.mark.parametrize(
    ("current", "new", "ok"),
    [
        ("scheduled", "in_progress", True),
        ("scheduled", "completed", True),
        ("scheduled", "cancelled", True),
        ("in_progress", "completed", True),
        ("in_progress", "scheduled", False),
        ("completed", "scheduled", False),
        ("cancelled", "in_progress", False),
        ("completed", "cancelled", False),
    ],
)
def test_session_transitions(current, new, ok):
    if ok:
        rules.check_session_transition(current, new)
    else:
        _refused("invalid_transition", rules.check_session_transition, current, new)


def test_session_window_and_plan_days():
    rules.check_session_window(NOW, NOW + timedelta(minutes=1))
    _refused("invalid_period", rules.check_session_window, NOW, NOW)
    rules.check_session_in_plan(date(2026, 10, 1), date(2026, 10, 1), date(2026, 10, 31))
    _refused("outside_plan", rules.check_session_in_plan, date(2026, 11, 1), date(2026, 10, 1), date(2026, 10, 31))


def test_closed_session_keeps_its_schedule():
    rules.check_session_change("completed", {"notes", "attendee_ids", "actual_duration_minutes", "drill_ids"})
    rules.check_session_change("scheduled", {"scheduled_start", "title"})
    _refused("session_closed", rules.check_session_change, "cancelled", {"scheduled_start", "notes"})


def test_completion_and_duration():
    _refused("not_started", rules.check_completion, NOW, NOW + timedelta(seconds=1))
    rules.check_completion(NOW, NOW)
    _refused("not_completed", rules.check_duration_allowed, "in_progress")
    assert rules.completed_duration(None, NOW, NOW + timedelta(minutes=90)) == 90
    assert rules.completed_duration(75, NOW, NOW + timedelta(minutes=90)) == 75


def test_not_in_future():
    rules.not_in_future(NOW, NOW, "recorded_at")
    _refused("in_future", rules.not_in_future, NOW + timedelta(seconds=1), NOW, "recorded_at")


@pytest.mark.parametrize(
    ("start", "end", "code"),
    [(-1, 5, "invalid_timestamp"), (5, 5, "invalid_timestamp"), (6, 5, "invalid_timestamp"), (0, 101, "outside_video")],
)
def test_segment_refusals(start, end, code):
    _refused(code, rules.check_segment, start, end, 100)


def test_segment_and_annotation_times_inside_the_video():
    rules.check_segment(0, 100, 100)
    rules.check_annotation_time(100, None, 100)
    rules.check_annotation_time(10, 10, 100)
    _refused("invalid_timestamp", rules.check_annotation_time, -0.5, None, 100)
    _refused("outside_video", rules.check_annotation_time, 100.5, None, 100)
    _refused("invalid_timestamp", rules.check_annotation_time, 10, 9, 100)
    _refused("outside_video", rules.check_annotation_time, 10, 101, 100)


def test_unique_keeps_first_order():
    assert rules.unique(["b", "a", "b"]) == ["b", "a"]
    assert rules.unique(None) == []
