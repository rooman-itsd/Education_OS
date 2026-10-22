"""Unit tests of the reopen window and the auto-close rule (domain layer): PRD main flow 7, MyTicketDetail.can_reopen
and POST /me/tickets/{id}/reopen."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from eos_helpdesk.domain.errors import DomainRuleError
from eos_helpdesk.domain.windows import can_reopen, due_for_auto_close, reopen_within_window

RESOLVED_AT = datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
WINDOW = 7
END = RESOLVED_AT + timedelta(days=WINDOW)
SECOND = timedelta(seconds=1)


def error_of(fn):
    with pytest.raises(DomainRuleError) as err:
        fn()
    return (err.value.code, err.value.kind, err.value.field)


# --- can_reopen: "True while resolved and inside the reopen window"


@pytest.mark.parametrize("now", [RESOLVED_AT, RESOLVED_AT + timedelta(days=3), END])
def test_a_resolved_ticket_can_be_reopened_inside_the_window(now):
    assert can_reopen("resolved", RESOLVED_AT, now, WINDOW) is True


def test_the_window_closes_after_its_last_moment():
    assert can_reopen("resolved", RESOLVED_AT, END + SECOND, WINDOW) is False


@pytest.mark.parametrize("status", ["new", "in_progress", "on_hold", "closed", "cancelled"])
def test_only_a_resolved_ticket_can_be_reopened(status):
    assert can_reopen(status, RESOLVED_AT, RESOLVED_AT, WINDOW) is False


def test_a_zero_day_window_allows_reopening_only_at_the_moment_of_resolution():
    assert can_reopen("resolved", RESOLVED_AT, RESOLVED_AT, 0) is True
    assert can_reopen("resolved", RESOLVED_AT, RESOLVED_AT + SECOND, 0) is False


def test_without_a_resolution_time_a_ticket_cannot_be_reopened():
    assert can_reopen("resolved", None, RESOLVED_AT, WINDOW) is False


# --- reopen: 409 "Not resolved, or the reopen window has passed"


def test_reopen_inside_the_window_moves_to_in_progress():
    assert reopen_within_window("resolved", RESOLVED_AT, END, WINDOW) == "in_progress"


def test_reopen_after_the_window_is_a_conflict():
    refused = error_of(lambda: reopen_within_window("resolved", RESOLVED_AT, END + SECOND, WINDOW))
    assert refused == ("reopen_window_passed", "conflict", "status")


@pytest.mark.parametrize("status", ["new", "in_progress", "on_hold", "closed", "cancelled"])
def test_reopen_of_a_ticket_that_is_not_resolved_is_a_conflict(status):
    refused = error_of(lambda: reopen_within_window(status, RESOLVED_AT, RESOLVED_AT, WINDOW))
    assert refused == ("transition_not_allowed", "conflict", "status")


# --- auto-close: "closes tickets resolved more than HELPDESK_AUTO_CLOSE_DAYS ago"


def test_a_ticket_resolved_more_than_the_days_ago_is_due():
    assert due_for_auto_close("resolved", RESOLVED_AT, END + SECOND, WINDOW) is True


@pytest.mark.parametrize("now", [RESOLVED_AT, RESOLVED_AT + timedelta(days=6), END])
def test_a_ticket_resolved_exactly_the_days_ago_or_less_is_not_due(now):
    assert due_for_auto_close("resolved", RESOLVED_AT, now, WINDOW) is False


@pytest.mark.parametrize("status", ["new", "in_progress", "on_hold", "closed", "cancelled"])
def test_only_resolved_tickets_are_auto_closed(status):
    assert due_for_auto_close(status, RESOLVED_AT, END + timedelta(days=30), WINDOW) is False


def test_without_a_resolution_time_a_ticket_is_not_auto_closed():
    assert due_for_auto_close("resolved", None, END + timedelta(days=30), WINDOW) is False


def test_windows_compare_instants_across_offsets():
    resolved_in_ist = datetime(2026, 10, 1, 17, 30, tzinfo=timezone(timedelta(hours=5, minutes=30)))  # 12:00 UTC
    assert can_reopen("resolved", resolved_in_ist, END, WINDOW) is True
    assert can_reopen("resolved", resolved_in_ist, END + SECOND, WINDOW) is False


# --- the number of days


@pytest.mark.parametrize("days", [-1, 1.5, "7", True, None])
def test_a_window_is_a_whole_number_of_days_at_least_zero(days):
    with pytest.raises(ValueError):
        can_reopen("resolved", RESOLVED_AT, RESOLVED_AT, days)
    with pytest.raises(ValueError):
        due_for_auto_close("resolved", RESOLVED_AT, RESOLVED_AT, days)


def test_an_unknown_status_is_invalid():
    assert error_of(lambda: can_reopen("open", RESOLVED_AT, RESOLVED_AT, WINDOW))[0] == "invalid_status"
