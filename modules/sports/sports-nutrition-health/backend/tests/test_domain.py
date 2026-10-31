"""Domain rules, without HTTP or a database."""

from datetime import UTC, date, datetime

import pytest
from eos_sports_nutrition_health.domain import rules
from eos_sports_nutrition_health.domain.rules import RuleViolationError

NOW = datetime(2026, 10, 29, 9, 0, tzinfo=UTC)


def _code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


def test_dates():
    rules.not_in_future(date(2026, 10, 30), NOW, "x")  # already the 30th east of UTC
    assert _code(rules.not_in_future, date(2026, 10, 31), NOW, "x") == "in_future"
    rules.not_before(None, date(2026, 1, 1), "a", "b")
    assert _code(rules.not_before, date(2026, 1, 1), date(2026, 1, 2), "a", "b") == "invalid_dates"


def test_a_review_ending_a_plan_completes_it():
    assert rules.plan_after_review("end", date(2026, 12, 1)) == {"status": "completed", "review_due_on": None}
    assert rules.plan_after_review("adjust", date(2026, 12, 1)) == {"review_due_on": date(2026, 12, 1)}
    assert rules.plan_after_review("continue", None) == {}
    assert _code(rules.check_plan_open, "archived") == "plan_closed"
    rules.check_plan_open("draft")


def test_appointment_status_moves():
    rules.check_new_appointment("scheduled")
    rules.check_new_appointment("completed")
    assert _code(rules.check_new_appointment, "cancelled") == "invalid_status"
    rules.check_appointment_change("scheduled", {"status": "no_show"})
    rules.check_appointment_change("completed", {"notes": "x"})
    assert _code(rules.check_appointment_change, "cancelled", {"status": "scheduled"}) == "appointment_closed"
    assert _code(rules.check_appointment_change, "completed", {"scheduled_at": NOW}) == "appointment_closed"
    assert _code(rules.check_held, datetime(2026, 10, 30, tzinfo=UTC), NOW) == "not_yet_held"
