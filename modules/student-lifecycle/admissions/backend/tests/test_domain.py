from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta

import pytest
from eos_admissions.domain import enums as e
from eos_admissions.domain.rules import (
    RankedEntry,
    RuleViolationError,
    check_can_offer,
    check_can_publish,
    check_documents_open,
    check_offer_decidable,
    effective_offer_status,
    funnel,
    generate_reference_number,
    normalise_email,
    rank_entries,
    validate_scores,
    validate_status_change,
)

NOW = datetime(2026, 10, 28, 12, 0, tzinfo=UTC)


def code_of(fn, *args) -> str:
    with pytest.raises(RuleViolationError) as exc:
        fn(*args)
    return exc.value.code


ALLOWED = [(current, target) for current, targets in e.STAFF_TRANSITIONS.items() for target in targets]


@pytest.mark.parametrize(("current", "target"), ALLOWED)
def test_every_allowed_staff_transition_passes(current, target):
    validate_status_change(current, target, "checked")


def test_under_review_may_repeat():
    validate_status_change(e.UNDER_REVIEW, e.UNDER_REVIEW, "transcript re-requested")


@pytest.mark.parametrize("current", sorted(e.TERMINAL))
@pytest.mark.parametrize("target", e.APPLICATION_STATUSES)
def test_terminal_status_refuses_any_change(current, target):
    assert code_of(validate_status_change, current, target, "reason") == "terminal_status"


DISALLOWED = [
    (current, target)
    for current in e.APPLICATION_STATUSES
    if current not in e.TERMINAL
    for target in e.APPLICATION_STATUSES
    if target not in e.STAFF_TRANSITIONS[current]
]


@pytest.mark.parametrize(("current", "target"), DISALLOWED)
def test_disallowed_staff_transition_is_invalid(current, target):
    assert code_of(validate_status_change, current, target, "reason") == "invalid_transition"


def test_staff_cannot_make_offer_or_decide_for_applicant():
    assert code_of(validate_status_change, e.ELIGIBLE, e.OFFERED, "r") == "invalid_transition"
    assert code_of(validate_status_change, e.OFFERED, e.ACCEPTED, "r") == "invalid_transition"
    assert code_of(validate_status_change, e.SUBMITTED, e.ELIGIBLE, "r") == "invalid_transition"


@pytest.mark.parametrize("reason", [None, "", "   "])
def test_status_change_needs_a_reason(reason):
    assert code_of(validate_status_change, e.SUBMITTED, e.UNDER_REVIEW, reason) == "reason_required"


def test_every_non_terminal_status_has_a_transition_row():
    assert set(e.STAFF_TRANSITIONS) == set(e.APPLICATION_STATUSES) - e.TERMINAL


def test_offer_only_on_eligible_without_open_offer():
    check_can_offer(e.ELIGIBLE, has_open_offer=False)
    assert code_of(check_can_offer, e.UNDER_REVIEW, False) == "not_eligible"
    assert code_of(check_can_offer, e.ACCEPTED, False) == "not_eligible"
    assert code_of(check_can_offer, e.OFFERED, True) == "offer_already_exists"


@pytest.mark.parametrize("status", sorted(e.DOCUMENTS_OPEN))
def test_documents_open_while_submitted_or_under_review(status):
    check_documents_open(status)


@pytest.mark.parametrize("status", sorted(set(e.APPLICATION_STATUSES) - e.DOCUMENTS_OPEN))
def test_documents_closed_otherwise(status):
    assert code_of(check_documents_open, status) == "documents_closed"


def test_effective_offer_status():
    assert effective_offer_status(e.OFFER_OPEN, None, NOW) == e.OFFER_OPEN
    assert effective_offer_status(e.OFFER_OPEN, NOW + timedelta(days=1), NOW) == e.OFFER_OPEN
    assert effective_offer_status(e.OFFER_OPEN, NOW, NOW) == e.OFFER_EXPIRED
    assert effective_offer_status(e.OFFER_OPEN, NOW - timedelta(seconds=1), NOW) == e.OFFER_EXPIRED
    assert effective_offer_status(e.ACCEPTED, NOW - timedelta(days=1), NOW) == e.ACCEPTED


def test_only_an_open_offer_can_be_decided():
    check_offer_decidable(e.OFFER_OPEN)
    for status in (e.OFFER_EXPIRED, e.ACCEPTED, e.DECLINED, e.WITHDRAWN):
        assert code_of(check_offer_decidable, status) == "no_open_offer"


def test_merit_list_publishes_once():
    check_can_publish(e.DRAFT)
    assert code_of(check_can_publish, e.PUBLISHED) == "merit_list_already_published"


def test_validate_scores():
    assert validate_scores([], {"a"}) == {}
    assert validate_scores([("a", 80.0), ("b", 75.5)], {"a", "b", "c"}) == {"a": 80.0, "b": 75.5}
    assert code_of(validate_scores, [("a", 1.0), ("a", 2.0)], {"a"}) == "duplicate_score"
    assert code_of(validate_scores, [("x", 1.0)], {"a"}) == "score_for_ineligible_application"


def t(minutes: int) -> datetime:
    return NOW + timedelta(minutes=minutes)


def test_rank_by_score_then_submission_then_unscored():
    candidates = [
        ("late-unscored", t(5)),
        ("tie-late", t(3)),
        ("top", t(4)),
        ("early-unscored", t(0)),
        ("tie-early", t(1)),
    ]
    scores = {"top": 95.0, "tie-late": 80.0, "tie-early": 80.0}
    assert rank_entries(candidates, scores) == [
        RankedEntry("top", 1, 95.0),
        RankedEntry("tie-early", 2, 80.0),
        RankedEntry("tie-late", 3, 80.0),
        RankedEntry("early-unscored", 4, None),
        RankedEntry("late-unscored", 5, None),
    ]


def test_rank_without_scores_is_submission_order():
    ranked = rank_entries([("b", t(2)), ("a", t(1)), ("c", t(3))], {})
    assert [(r.application_id, r.rank) for r in ranked] == [("a", 1), ("b", 2), ("c", 3)]


def test_rank_does_not_depend_on_input_order():
    candidates = [("x", t(1)), ("y", t(1)), ("z", t(0))]
    assert rank_entries(candidates, {}) == rank_entries(list(reversed(candidates)), {})


def test_rank_of_nothing_is_empty():
    assert rank_entries([], {"a": 1.0}) == []


def test_funnel_of_nothing_is_zero_with_every_status():
    report = funnel({})
    assert report["total"] == 0
    assert report["stages"] == {"applied": 0, "eligible": 0, "offered": 0, "accepted": 0}
    assert set(report["by_status"]) == set(e.APPLICATION_STATUSES)


def test_funnel_stages():
    report = funnel(
        {e.SUBMITTED: 4, e.UNDER_REVIEW: 3, e.ELIGIBLE: 2, e.OFFERED: 2, e.ACCEPTED: 5, e.DECLINED: 1, e.REJECTED: 3}
    )
    assert report["total"] == 20
    assert report["stages"] == {"applied": 20, "eligible": 10, "offered": 8, "accepted": 5}
    assert report["by_status"][e.WITHDRAWN] == 0


def test_reference_number_format():
    ref = generate_reference_number(when=NOW)
    assert re.fullmatch(r"ADM-2026-[0-9A-F]{6}", ref)
    assert generate_reference_number(prefix="APP", when=NOW).startswith("APP-2026-")
    assert re.fullmatch(r"ADM-\d{4}-[0-9A-F]{6}", generate_reference_number())


def test_reference_numbers_vary():
    assert len({generate_reference_number(when=NOW) for _ in range(50)}) > 1


def test_normalise_email():
    assert normalise_email("  Ana@Example.COM ") == "ana@example.com"
