"""Domain rules: pure functions, no framework and no database."""

from datetime import date

import pytest
from eos_iqac_accreditation.domain import accreditation as rules
from eos_iqac_accreditation.domain.errors import DomainRuleError

D = date(2026, 11, 5)


def refused(fn, *args, **kwargs) -> tuple[str, str]:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kwargs)
    return e.value.kind, e.value.code


def test_error_kinds_are_the_three_the_api_maps():
    assert rules.DomainRuleError("c", "m", kind="conflict").kind == "conflict"
    with pytest.raises(ValueError):
        DomainRuleError("c", "m", kind="other")


def test_cycle_moves_are_the_four_in_order():
    for current, target in rules.CYCLE_MOVES:
        extra = (D, True) if target == "submitted" else (None, True)
        assert rules.cycle_move(current, target, *extra) is None
    every = {(a, b) for a in rules.CYCLE_STATUSES for b in rules.CYCLE_STATUSES}
    for current, target in every - rules.CYCLE_MOVES:
        assert refused(rules.cycle_move, current, target, D, True) == ("conflict", "transition_not_allowed")


def test_submitting_needs_the_date_then_every_response_accepted():
    assert refused(rules.cycle_move, "under_review", "submitted", None, False) == ("invalid", "submitted_on_required")
    assert refused(rules.cycle_move, "under_review", "submitted", D, False) == ("conflict", "responses_not_accepted")
    assert refused(rules.cycle_move, "under_review", "submitted", date(2300, 1, 1), True) == (
        "invalid",
        "date_out_of_range",
    )
    assert rules.cycle_move("under_review", "submitted", D, True) is None


def test_period_must_end_after_it_starts():
    assert rules.check_period(date(2025, 4, 1), date(2025, 4, 2)) is None
    for end in (date(2025, 4, 1), date(2025, 3, 31)):
        assert refused(rules.check_period, date(2025, 4, 1), end) == ("invalid", "period_end_not_after_start")


def test_where_a_cycle_takes_changes():
    assert rules.check_cycle_planning("planning") is None
    assert refused(rules.check_cycle_planning, "collecting")[0] == "conflict"
    assert {s for s in rules.CYCLE_STATUSES if s in rules.ASSIGNABLE} == {"planning", "collecting"}
    assert {s for s in rules.CYCLE_STATUSES if s in rules.RESPONDING} == {"collecting", "under_review"}
    assert {s for s in rules.CYCLE_STATUSES if s in rules.OPEN_CYCLE} == set(rules.CYCLE_STATUSES) - {"closed"}
    assert refused(rules.check_assignable, "under_review") == ("conflict", "cycle_not_assignable")
    assert refused(rules.check_cycle_responding, "planning") == ("conflict", "cycle_not_collecting")


def test_a_metric_is_assignable_when_active_and_of_the_cycles_framework():
    assert rules.check_metric_assignable("f1", "f1", True) is None
    assert refused(rules.check_metric_assignable, "f2", "f1", True) == ("invalid", "metric_not_in_framework")
    assert refused(rules.check_metric_assignable, "f1", "f1", False) == ("invalid", "metric_inactive")
    assert refused(rules.check_framework_active, False) == ("invalid", "framework_inactive")


def test_the_owner_edits_only_pending_or_returned_responses():
    for status in ("pending", "returned"):
        assert rules.check_response_editable(status) is None
    for status in ("submitted", "accepted"):
        assert refused(rules.check_response_editable, status) == ("conflict", "response_not_editable")
    assert rules.check_not_accepted("submitted") is None
    assert refused(rules.check_not_accepted, "accepted") == ("conflict", "response_accepted")
    assert refused(rules.check_submitted, "pending") == ("conflict", "response_not_submitted")


def test_what_a_metric_kind_asks_for():
    assert rules.check_value_allowed("quantitative", 3.0) is None
    assert rules.check_value_allowed("qualitative", None) is None
    assert refused(rules.check_value_allowed, "qualitative", 0) == ("invalid", "value_not_allowed")
    assert rules.check_ready_to_submit("quantitative", 0.0, None) is None
    assert rules.check_ready_to_submit("qualitative", None, " text ") is None
    assert refused(rules.check_ready_to_submit, "quantitative", None, "n") == ("invalid", "value_required")
    assert refused(rules.check_ready_to_submit, "qualitative", 1, "  ") == ("invalid", "narrative_required")


def test_a_return_comment_is_three_characters_without_spaces():
    assert rules.check_return_comment("abc") is None
    assert rules.check_return_comment("  abc ") is None
    for comment in (None, "", "ab", "  a  "):
        assert refused(rules.check_return_comment, comment) == ("invalid", "comment_required")


def test_evidence_kinds_take_their_own_field_only():
    ref = {"module": "m", "entity": "e", "id": "1"}
    assert rules.check_evidence("link", "https://e.edu", None) is None
    assert rules.check_evidence("reference", None, ref) is None
    assert refused(rules.check_evidence, "link", None, None)[0] == "invalid"
    assert refused(rules.check_evidence, "link", "https://e.edu", ref)[0] == "invalid"
    assert refused(rules.check_evidence, "reference", None, None)[0] == "invalid"
    assert refused(rules.check_evidence, "reference", "https://e.edu", ref)[0] == "invalid"


def test_response_overdue_is_pending_or_returned_and_past_due():
    assert rules.is_response_overdue("pending", date(2026, 11, 4), D)
    assert rules.is_response_overdue("returned", date(2026, 11, 4), D)
    assert not rules.is_response_overdue("pending", D, D)
    for status in ("submitted", "accepted"):
        assert not rules.is_response_overdue(status, date(2020, 1, 1), D)


def test_action_item_moves_and_overdue():
    assert {(a, b) for a in rules.ACTION_STATUSES for b in rules.ACTION_STATUSES if (a, b) in rules.ACTION_MOVES} == {
        ("open", "in_progress"),
        ("in_progress", "done"),
        ("open", "cancelled"),
        ("in_progress", "cancelled"),
    }
    assert rules.action_move("open", "in_progress") is None
    for current, target in (("open", "done"), ("in_progress", "in_progress"), ("done", "cancelled")):
        assert refused(rules.action_move, current, target) == ("conflict", "transition_not_allowed")
    for status in ("done", "cancelled"):
        assert refused(rules.check_action_live, status) == ("conflict", "action_item_closed")
    assert rules.is_action_overdue("open", date(2026, 11, 4), D) and rules.is_action_overdue(
        "in_progress", date(2026, 11, 4), D
    )
    assert not rules.is_action_overdue("open", D, D)
    assert not rules.is_action_overdue("done", date(2020, 1, 1), D)


def test_due_soon_is_from_today_up_to_the_window_by_subtraction():
    assert rules.is_action_due_soon("open", D, D, 14)
    assert rules.is_action_due_soon("in_progress", date(2026, 11, 19), D, 14)
    assert not rules.is_action_due_soon("open", date(2026, 11, 20), D, 14)
    assert not rules.is_action_due_soon("open", date(2026, 11, 4), D, 14)
    assert not rules.is_action_due_soon("cancelled", D, D, 14)
    assert not rules.is_action_due_soon("open", date.max, D, 14)  # no date sum, nothing overflows


def test_dates_outside_the_module_range_are_refused():
    assert rules.check_date(rules.MIN_DATE, "d") is None and rules.check_date(rules.MAX_DATE, "d") is None
    for bad in (date(1899, 12, 31), date(2200, 1, 1), date.min, date.max):
        assert refused(rules.check_date, bad, "d") == ("invalid", "date_out_of_range")
