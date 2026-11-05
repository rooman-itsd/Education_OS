"""The rules in domain/rules.py, with no database and no HTTP."""

from datetime import UTC, datetime, timedelta

import pytest
from eos_productions.domain import rules as r

NOW = datetime(2026, 11, 2, 9, 0, tzinfo=UTC)
SETTINGS = r.ProductionRules()


def test_a_production_must_end_after_it_starts():
    with pytest.raises(r.RuleViolationError) as e:
        r.check_schedule(NOW, NOW, None, SETTINGS)
    assert e.value.code == "invalid_dates"
    with pytest.raises(r.RuleViolationError):
        r.check_schedule(NOW, NOW - timedelta(hours=1), None, SETTINGS)


def test_an_implausibly_long_run_is_refused_as_a_typo():
    with pytest.raises(r.RuleViolationError) as e:
        r.check_schedule(NOW, NOW + timedelta(hours=SETTINGS.max_run_hours + 1), None, SETTINGS)
    assert e.value.code == "run_too_long"
    assert e.value.extra["limit_hours"] == SETTINGS.max_run_hours
    r.check_schedule(NOW, NOW + timedelta(hours=SETTINGS.max_run_hours), None, SETTINGS)  # the limit itself is fine


def test_the_call_time_may_not_be_after_the_start():
    r.check_schedule(NOW, NOW + timedelta(hours=2), NOW - timedelta(minutes=30), SETTINGS)
    r.check_schedule(NOW, NOW + timedelta(hours=2), NOW, SETTINGS)
    with pytest.raises(r.RuleViolationError) as e:
        r.check_schedule(NOW, NOW + timedelta(hours=2), NOW + timedelta(minutes=1), SETTINGS)
    assert e.value.code == "invalid_call_time"


def test_a_production_in_the_past_is_still_a_valid_schedule():
    """An academy records a recital that already happened; only the order of the dates is a rule."""
    past = NOW - timedelta(days=30)
    r.check_schedule(past, past + timedelta(hours=3), None, SETTINGS)


def test_the_default_call_time_comes_before_the_start():
    assert r.default_call_time(NOW, SETTINGS) == NOW - timedelta(minutes=SETTINGS.default_call_minutes)


def test_a_short_preparation_window_is_a_warning_not_a_refusal():
    assert r.preparation_is_short(NOW + timedelta(days=1), NOW, SETTINGS) is True
    assert r.preparation_is_short(NOW + timedelta(days=30), NOW, SETTINGS) is False


def test_each_action_names_the_status_that_refused_it():
    with pytest.raises(r.RuleViolationError) as e:
        r.check_action("complete", r.PLANNED)
    assert e.value.code == "wrong_status"
    assert e.value.extra["status"] == r.PLANNED
    assert "planned" in e.value.message


@pytest.mark.parametrize("action", sorted(r.ALLOWED_FROM))
def test_nothing_may_be_done_to_a_completed_or_cancelled_production(action):
    for status in (r.COMPLETED, r.CANCELLED):
        with pytest.raises(r.RuleViolationError):
            r.check_action(action, status)


def test_preparation_only_starts_from_planned_and_completion_only_from_scheduled():
    r.check_action("start_preparation", r.PLANNED)
    with pytest.raises(r.RuleViolationError):
        r.check_action("start_preparation", r.IN_PREPARATION)
    r.check_action("complete", r.SCHEDULED)
    with pytest.raises(r.RuleViolationError):
        r.check_action("complete", r.IN_PREPARATION)


def test_a_scheduled_production_can_still_be_moved():
    for status in (r.PLANNED, r.IN_PREPARATION, r.SCHEDULED):
        r.check_action("schedule", status)


def test_a_part_can_only_be_answered_once_and_only_while_the_production_is_alive():
    r.check_response(r.INVITED, r.SCHEDULED)
    for already in (r.CONFIRMED, r.DECLINED, r.WITHDRAWN):
        with pytest.raises(r.RuleViolationError) as e:
            r.check_response(already, r.SCHEDULED)
        assert e.value.code == "already_answered"
    with pytest.raises(r.RuleViolationError) as e:
        r.check_response(r.INVITED, r.CANCELLED)
    assert e.value.code == "wrong_status"


def test_only_a_live_assignment_can_be_withdrawn():
    for live in r.LIVE_ROLE_STATUSES:
        r.check_withdrawal(live)
    for finished in (r.DECLINED, r.WITHDRAWN):
        with pytest.raises(r.RuleViolationError):
            r.check_withdrawal(finished)


def test_unknown_kinds_are_refused():
    r.check_kind("hackathon")
    with pytest.raises(r.RuleViolationError):
        r.check_kind("concert")
    r.check_role_kind("crew")
    with pytest.raises(r.RuleViolationError):
        r.check_role_kind("understudy")


def test_a_task_without_a_due_date_is_never_overdue():
    assert r.is_overdue(None, NOW) is False
    assert r.is_overdue(NOW - timedelta(minutes=1), NOW) is True
    assert r.is_overdue(NOW + timedelta(minutes=1), NOW) is False
