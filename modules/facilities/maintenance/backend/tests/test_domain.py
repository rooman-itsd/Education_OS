"""Unit tests of the pure maintenance rules (domain layer)."""

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from eos_maintenance.domain.rules import (
    RuleViolationError,
    SlaHours,
    add_interval,
    auto_close_due,
    breaches,
    check_assign,
    check_cancel,
    check_close,
    check_hold,
    check_reopen,
    check_resolve,
    check_start,
    check_target,
    check_work_entry,
    due_times,
    effective_sla,
    initial_status,
    money,
    reopen_status,
    same_target,
    should_raise,
    sort_key,
)

NOW = datetime(2026, 10, 12, 8, 0, tzinfo=UTC)
SLA = SlaHours(
    response={"urgent": 1, "high": 4, "medium": 24, "low": 72},
    resolution={"urgent": 8, "high": 48, "medium": 120, "low": 336},
)


def test_category_sla_override_wins_per_priority():
    sla = effective_sla(SLA, {"response_hours": {"urgent": 2}})
    assert sla.response["urgent"] == 2
    assert sla.response["high"] == 4
    assert sla.resolution == SLA.resolution


def test_due_times_add_the_hours_and_push_out_by_time_on_hold():
    response, resolution = due_times(NOW, "high", SLA)
    assert response == NOW + timedelta(hours=4)
    assert resolution == NOW + timedelta(hours=48)
    _, paused = due_times(NOW, "high", SLA, held_minutes=90)
    assert paused == NOW + timedelta(hours=48, minutes=90)


def test_breaches_while_timers_run_and_after_they_stop():
    due = {"response_due_at": NOW, "resolution_due_at": NOW + timedelta(hours=8)}
    later = NOW + timedelta(hours=1)
    assert breaches(status="open", now=later, started_at=None, resolved_at=None, **due) == ["response"]
    # started in time: the response timer stopped before it passed
    on_time = NOW - timedelta(minutes=5)
    assert breaches(status="in_progress", now=later, started_at=on_time, resolved_at=None, **due) == []
    # nothing runs on hold
    assert breaches(status="on_hold", now=NOW + timedelta(days=2), started_at=on_time, resolved_at=None, **due) == []
    # resolved late stays breached
    late = NOW + timedelta(hours=9)
    assert breaches(status="closed", now=late, started_at=on_time, resolved_at=late, **due) == ["resolution"]
    # a flag published by the sweep is kept
    assert breaches(
        status="in_progress", now=NOW, started_at=on_time, resolved_at=None, flagged=(True, False), **due
    ) == ["response"]


def test_one_default_assignee_goes_straight_to_assigned():
    assert initial_status(["u-1"]) == ("assigned", "u-1")
    assert initial_status(["u-1", "u-2"]) == ("open", None)
    assert initial_status([]) == ("open", None)


def test_lifecycle_transitions():
    assert check_assign("open") == "assigned"
    assert check_assign("in_progress") == "in_progress"  # reassigning keeps the work going
    with pytest.raises(RuleViolationError) as e:
        check_assign("resolved")
    assert e.value.status == 409
    assert check_start("assigned", True) == "in_progress"
    assert check_start("on_hold", True) == "in_progress"
    with pytest.raises(RuleViolationError):
        check_start("open", False)
    assert check_hold("in_progress", "waiting_parts") == "on_hold"
    with pytest.raises(RuleViolationError):
        check_hold("assigned", "waiting_parts")
    with pytest.raises(RuleViolationError):
        check_hold("in_progress", "lunch")
    assert check_resolve("in_progress", "Replaced the fuse") == "resolved"
    with pytest.raises(RuleViolationError) as e:
        check_resolve("in_progress", "  ")
    assert e.value.code == "note_required"
    assert check_close("resolved") == "closed"
    with pytest.raises(RuleViolationError):
        check_close("in_progress")


def test_reopen_only_within_the_window():
    check_reopen("resolved", NOW, NOW + timedelta(days=7), window_days=7)
    with pytest.raises(RuleViolationError) as e:
        check_reopen("closed", NOW, NOW + timedelta(days=7, seconds=1), window_days=7)
    assert e.value.code == "reopen_window_passed"
    with pytest.raises(RuleViolationError):
        check_reopen("in_progress", None, NOW, window_days=7)
    assert reopen_status(True) == "assigned"
    assert reopen_status(False) == "open"


def test_reporter_cancels_only_before_work_starts():
    assert check_cancel("assigned", manager=False) == "cancelled"
    with pytest.raises(RuleViolationError):
        check_cancel("in_progress", manager=False)
    assert check_cancel("in_progress", manager=True) == "cancelled"
    with pytest.raises(RuleViolationError):
        check_cancel("resolved", manager=True)


def test_auto_close_after_the_configured_days():
    assert not auto_close_due(NOW, NOW + timedelta(days=2, hours=23), 3)
    assert auto_close_due(NOW, NOW + timedelta(days=3), 3)


def test_targets_need_an_id_unless_they_are_a_location():
    check_target("asset", "AST-1", "AST-1 · Lab 2")
    check_target("location", None, "Block B corridor")
    with pytest.raises(RuleViolationError):
        check_target("asset", None, "Somewhere")
    with pytest.raises(RuleViolationError):
        check_target("location", None, " ")


def test_same_target_compares_ids_or_location_labels():
    assert same_target(("asset", "a1", "x"), ("asset", "a1", "y"))
    assert not same_target(("asset", "a1", "x"), ("resource", "a1", "x"))
    assert same_target(("location", None, "Block B "), ("location", None, "block b"))


def test_intervals_move_from_the_scheduled_date_and_clamp_month_ends():
    assert add_interval(date(2026, 10, 12), 10, "days") == date(2026, 10, 22)
    assert add_interval(date(2026, 10, 12), 2, "weeks") == date(2026, 10, 26)
    assert add_interval(date(2026, 1, 31), 1, "months") == date(2026, 2, 28)
    assert add_interval(date(2026, 11, 15), 3, "months") == date(2027, 2, 15)


def test_schedule_raises_lead_days_early_and_never_twice():
    due = date(2026, 10, 15)
    assert should_raise(active=True, has_open_ticket=False, next_due_on=due, lead_days=3, today=date(2026, 10, 12))
    assert not should_raise(active=True, has_open_ticket=False, next_due_on=due, lead_days=2, today=date(2026, 10, 12))
    assert not should_raise(active=True, has_open_ticket=True, next_due_on=due, lead_days=3, today=date(2026, 10, 14))
    assert not should_raise(active=False, has_open_ticket=False, next_due_on=due, lead_days=3, today=date(2026, 10, 14))


def test_money_is_decimal_with_two_places():
    assert money("1250.50", "INR") == Decimal("1250.50")
    for bad in (("1.234", "INR"), ("-1", "INR"), ("abc", "INR"), ("10", "inr")):
        with pytest.raises(RuleViolationError):
            money(*bad)


def test_reporters_log_notes_only():
    check_work_entry("note", {"note": "Still dripping"}, can_work=False)
    with pytest.raises(RuleViolationError) as e:
        check_work_entry("time", {"minutes": 30}, can_work=False)
    assert e.value.status == 403
    check_work_entry("time", {"minutes": 30}, can_work=True)
    with pytest.raises(RuleViolationError):
        check_work_entry("part", {}, can_work=True)


def test_breached_tickets_sort_first_then_by_priority():
    keys = [
        sort_key("low", False, NOW),
        sort_key("urgent", False, NOW),
        sort_key("medium", True, NOW),
    ]
    assert sorted(keys)[0] == sort_key("medium", True, NOW)
    assert sorted(keys)[1] == sort_key("urgent", False, NOW)
