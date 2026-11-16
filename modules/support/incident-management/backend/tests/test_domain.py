"""Domain rules, without a database or web framework."""

from datetime import date

import pytest
from eos_incident_management.domain import incidents as inc
from eos_incident_management.domain import problems as prb
from eos_incident_management.domain.errors import DomainRuleError
from eos_incident_management.domain.stats import open_counts


def refused(fn, *args, **kwargs) -> tuple[str, str]:
    with pytest.raises(DomainRuleError) as e:
        fn(*args, **kwargs)
    return e.value.kind, e.value.code


# ---------------------------------------------------------------- incidents

ALLOWED_INCIDENT_MOVES = {
    ("open", "investigating"),
    ("investigating", "mitigated"),
    ("mitigated", "investigating"),
    ("investigating", "resolved"),
    ("mitigated", "resolved"),
    ("resolved", "closed"),
    ("resolved", "investigating"),
    ("open", "cancelled"),
    ("investigating", "cancelled"),
}


@pytest.mark.parametrize("current", inc.INCIDENT_STATUSES)
@pytest.mark.parametrize("target", inc.TARGET_STATUSES)
def test_incident_moves_are_exactly_the_contract_ones(current, target):
    extra = {"resolution_summary": "Fixed", "note": "Because"}
    if (current, target) in ALLOWED_INCIDENT_MOVES:
        assert inc.move(current, target, **extra) == target
    else:
        assert refused(inc.move, current, target, **extra) == ("conflict", "transition_not_allowed")


def test_incident_notes_and_summary_are_required():
    assert refused(inc.move, "investigating", "resolved") == ("invalid", "resolution_summary_required")
    assert refused(inc.move, "mitigated", "resolved", resolution_summary="  ") == (
        "invalid",
        "resolution_summary_required",
    )
    assert refused(inc.move, "open", "cancelled") == ("invalid", "note_required")
    assert refused(inc.move, "resolved", "investigating", note=" ") == ("invalid", "note_required")
    assert inc.move("open", "investigating") == "investigating"  # no note needed
    assert inc.move("mitigated", "investigating") == "investigating"  # not a reopen
    assert refused(inc.move, "open", "open") == ("invalid", "invalid_status")


def test_reopen_is_only_from_resolved():
    assert inc.is_reopen("resolved", "investigating")
    assert not inc.is_reopen("mitigated", "investigating")


@pytest.mark.parametrize("status", ["closed", "cancelled"])
def test_closed_or_cancelled_incident_is_not_editable(status):
    assert refused(inc.check_editable, status) == ("conflict", "incident_closed")


@pytest.mark.parametrize("status", ["open", "investigating", "mitigated", "resolved"])
def test_other_incidents_are_editable(status):
    inc.check_editable(status)


def test_blank_text_is_refused():
    assert refused(inc.check_text, "   ", "title") == ("invalid", "title_blank")
    inc.check_text("Wi-Fi", "title")


# ---------------------------------------------------------------- problems

ALLOWED_PROBLEM_MOVES = {
    ("open", "investigating"),
    ("investigating", "known_error"),
    ("investigating", "resolved"),
    ("known_error", "resolved"),
    ("resolved", "closed"),
}


@pytest.mark.parametrize("current", prb.PROBLEM_STATUSES)
@pytest.mark.parametrize("target", prb.TARGET_STATUSES)
def test_problem_moves_are_exactly_the_contract_ones(current, target):
    if (current, target) in ALLOWED_PROBLEM_MOVES:
        assert prb.move(current, target, workaround="Reboot", rca_status="published") == target
    else:
        assert refused(prb.move, current, target, workaround="Reboot", rca_status="published") == (
            "conflict",
            "transition_not_allowed",
        )


def test_known_error_needs_a_workaround_and_resolved_a_published_rca():
    assert refused(prb.move, "investigating", "known_error", workaround=None, rca_status=None) == (
        "invalid",
        "workaround_required",
    )
    assert refused(prb.move, "investigating", "known_error", workaround=" ", rca_status=None)[1] == (
        "workaround_required"
    )
    assert refused(prb.move, "investigating", "resolved", workaround=None, rca_status=None) == (
        "conflict",
        "rca_not_published",
    )
    assert refused(prb.move, "known_error", "resolved", workaround="x", rca_status="draft")[1] == "rca_not_published"
    assert refused(prb.move, "open", "open", workaround=None, rca_status=None) == ("invalid", "invalid_status")


def test_problem_edit_and_link_rules():
    assert refused(prb.check_editable, "closed") == ("conflict", "problem_closed")
    prb.check_editable("resolved")
    assert refused(prb.check_can_link, "closed") == ("conflict", "problem_closed")
    prb.check_can_link("known_error")
    assert refused(prb.check_can_add_action, "closed") == ("conflict", "problem_closed")
    assert refused(prb.check_workaround_kept, "known_error", None) == ("invalid", "workaround_required")
    prb.check_workaround_kept("investigating", None)


def test_rca_draft_then_published_and_read_only():
    prb.check_rca_editable("draft")
    assert prb.publish_rca("draft") == "published"
    assert refused(prb.publish_rca, "published") == ("conflict", "rca_published")
    assert refused(prb.check_rca_editable, "published") == ("conflict", "rca_published")


def test_actions_overdue_and_due_dates():
    today = date(2026, 11, 4)
    assert prb.is_overdue("open", date(2026, 11, 3), today)
    assert not prb.is_overdue("open", today, today)  # the due date itself is not overdue yet
    assert not prb.is_overdue("done", date(2026, 1, 1), today)
    assert not prb.is_overdue("cancelled", date(2026, 1, 1), today)
    prb.check_due_date(today, today)
    assert refused(prb.check_due_date, date(2026, 11, 3), today) == ("invalid", "due_date_in_past")
    for status in ("done", "cancelled"):
        assert refused(prb.check_action_editable, status) == ("conflict", "action_closed")
    prb.check_action_editable("open")


# ---------------------------------------------------------------- statistics


def test_open_counts_by_severity_and_status():
    counts = open_counts(
        [
            ("open", "critical"),
            ("investigating", "critical"),
            ("mitigated", "low"),
            ("resolved", "high"),
            ("closed", "critical"),
            ("cancelled", "medium"),
        ]
    )
    assert counts.total_open == 3
    assert [(c.severity, c.count) for c in counts.by_severity] == [
        ("critical", 2),
        ("high", 0),
        ("medium", 0),
        ("low", 1),
    ]
    assert [(c.status, c.count) for c in counts.by_status] == [("open", 1), ("investigating", 1), ("mitigated", 1)]


def test_open_counts_of_nothing_has_zero_rows():
    counts = open_counts([])
    assert counts.total_open == 0
    assert [c.count for c in counts.by_severity] == [0, 0, 0, 0]
    assert [c.count for c in counts.by_status] == [0, 0, 0]


def test_unknown_error_kind_is_a_programming_error():
    with pytest.raises(ValueError):
        DomainRuleError("x", "y", kind="other")
