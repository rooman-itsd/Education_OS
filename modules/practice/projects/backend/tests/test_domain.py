"""Domain rules, without HTTP or a database."""

from datetime import UTC, date, datetime

import pytest
from eos_projects.application import service
from eos_projects.domain import rules
from eos_projects.domain.rules import MILESTONE_TRANSITIONS, PROJECT_TRANSITIONS, RuleViolationError

TODAY = date(2026, 11, 4)


def code(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as e:
        fn(*args)
    return e.value.code


def test_project_transitions():
    assert rules.transition(PROJECT_TRANSITIONS, "approve", "proposed") == "active"
    assert rules.transition(PROJECT_TRANSITIONS, "reject", "proposed") == "rejected"
    assert rules.transition(PROJECT_TRANSITIONS, "submit", "active") == "submitted"
    assert rules.transition(PROJECT_TRANSITIONS, "complete", "submitted") == "completed"
    assert rules.transition(PROJECT_TRANSITIONS, "return", "submitted") == "active"
    assert rules.transition(PROJECT_TRANSITIONS, "cancel", "proposed") == "cancelled"
    assert rules.transition(PROJECT_TRANSITIONS, "cancel", "active") == "cancelled"
    for action, status in (
        ("approve", "active"),
        ("submit", "proposed"),
        ("complete", "active"),
        ("cancel", "submitted"),
        ("cancel", "completed"),
        ("cancel", "cancelled"),
    ):
        assert code(rules.transition, PROJECT_TRANSITIONS, action, status) == "invalid_status"


def test_milestone_transitions():
    assert rules.transition(MILESTONE_TRANSITIONS, "submit", "pending") == "submitted"
    assert rules.transition(MILESTONE_TRANSITIONS, "submit", "returned") == "submitted"
    assert rules.transition(MILESTONE_TRANSITIONS, "accept", "submitted") == "accepted"
    assert rules.transition(MILESTONE_TRANSITIONS, "return", "submitted") == "returned"
    assert rules.transition(MILESTONE_TRANSITIONS, "cancel", "submitted") == "cancelled"
    for action, status in (
        ("submit", "submitted"),
        ("submit", "accepted"),
        ("cancel", "accepted"),
        ("accept", "pending"),
    ):
        assert code(rules.transition, MILESTONE_TRANSITIONS, action, status) == "invalid_status"


def test_team_rules():
    rules.check_team(["a", "b"], "a", ["g"])
    assert code(rules.check_team, ["a", "b"], None, ["g"]) == "no_lead"
    assert code(rules.check_team, ["a"], "z", ["g"]) == "no_lead"
    assert code(rules.check_team, ["a"], "a", []) == "guide_required"
    assert code(rules.check_team, ["a", "b"], "a", ["b"]) == "member_is_guide"
    assert code(rules.check_guides, [], ["a"]) == "guide_required"


def test_period_reason_review_and_evaluation():
    rules.check_period(date(2026, 8, 1), date(2026, 8, 1))
    assert code(rules.check_period, date(2026, 8, 2), date(2026, 8, 1)) == "invalid_dates"
    assert rules.check_reason("  Out of scope  ", "reject") == "Out of scope"
    assert code(rules.check_reason, "no", "reject") == "reason_required"
    assert code(rules.check_reason, None, "reject") == "reason_required"
    rules.check_review("accepted", None)
    assert code(rules.check_review, "returned", "  ") == "comments_required"
    rules.check_evaluation("returned", None)
    assert code(rules.check_evaluation, "completed", "") == "outcome_required"
    assert code(rules.check_not_closed, "completed") == "invalid_status"
    rules.check_not_closed("submitted")


def test_overdue_and_progress():
    assert rules.is_overdue("pending", date(2026, 11, 3), TODAY)
    assert rules.is_overdue("returned", date(2026, 11, 3), TODAY)
    assert not rules.is_overdue("pending", TODAY, TODAY)  # due today is not yet overdue
    assert not rules.is_overdue("submitted", date(2026, 11, 1), TODAY)
    assert not rules.is_overdue("accepted", date(2026, 11, 1), TODAY)
    assert rules.progress(["accepted", "pending", "cancelled", "accepted"]) == (2, 3)
    assert rules.progress([]) == (0, 0)
    assert rules.not_accepted([("a", "accepted"), ("b", "pending"), ("c", "cancelled"), ("d", "returned")]) == [
        "b",
        "d",
    ]
    assert rules.days_between(TODAY, date(2026, 11, 1)) == -3


def test_business_date_is_asia_kolkata(monkeypatch):
    # 18:29 UTC is still 3 November in India (23:59); 18:30 UTC is already 4 November.
    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 11, 3, 18, 29, tzinfo=UTC))
    assert service.today() == date(2026, 11, 3)
    monkeypatch.setattr(service, "clock", lambda: datetime(2026, 11, 3, 18, 30, tzinfo=UTC))
    assert service.today() == date(2026, 11, 4)
    assert service.business_date(datetime(2026, 11, 3, 20, 0)) == date(2026, 11, 4)  # naive values are UTC
