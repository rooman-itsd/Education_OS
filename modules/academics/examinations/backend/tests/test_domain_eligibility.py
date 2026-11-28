"""The eligibility rules (decisions D2 and D7, issue #325): which registration makes a candidate in which cycle, the
attendance input against a cycle's own minimum, and how the four inputs decide a status."""

from decimal import Decimal

import pytest
from eos_examinations.domain import eligibility as el


@pytest.mark.parametrize(
    ("cycle_type", "registration_type", "expected"),
    [
        ("internal", "regular", True),
        ("mid_term", "regular", True),
        ("end_term", "regular", True),
        ("internal", "supplementary", False),
        ("end_term", "backlog", False),
        ("supplementary", "supplementary", True),
        ("supplementary", "backlog", True),
        ("supplementary", "regular", False),
    ],
)
def test_a_registration_makes_a_candidate_only_in_the_cycles_its_type_names(cycle_type, registration_type, expected):
    assert el.registration_makes_candidate(cycle_type, registration_type) is expected


def test_every_registration_type_the_contract_has_is_covered_by_some_cycle():
    for kind in el.REGISTRATION_TYPES:
        assert any(el.registration_makes_candidate(c, kind) for c in ("end_term", "supplementary")), kind


@pytest.mark.parametrize(
    ("percent", "minimum", "expected"),
    [
        (None, None, el.NOT_REQUIRED),  # the cycle sets no minimum
        (Decimal("10"), None, el.NOT_REQUIRED),
        (None, Decimal("75"), el.UNAVAILABLE),  # a minimum and no reading: never silently eligible
        (Decimal("75"), Decimal("75"), el.PASSED),  # at least: the minimum itself passes
        (Decimal("74.99"), Decimal("75"), el.FAILED),
        (Decimal("100"), Decimal("75"), el.PASSED),
        (Decimal("0"), Decimal("0"), el.PASSED),
    ],
)
def test_attendance_is_judged_against_the_minimum_of_the_cycle(percent, minimum, expected):
    assert el.attendance_input(percent, minimum) == expected


def test_the_same_attendance_passes_one_cycle_and_fails_another():
    reading = Decimal("70")
    assert el.attendance_input(reading, Decimal("65")) == el.PASSED  # a cycle with a lower minimum
    assert el.attendance_input(reading, Decimal("75")) == el.FAILED  # a cycle with a higher one


def outcomes(**over) -> dict:
    base = {
        el.REGISTRATION: el.PASSED,
        el.STUDENT_STATUS: el.PASSED,
        el.ATTENDANCE: el.PASSED,
        el.DUES: el.NOT_REQUIRED,
    }
    return {**base, **over}


def test_all_inputs_passed_is_eligible_and_a_not_required_input_counts_as_met():
    d = el.decide(outcomes())
    assert (d.status, d.reasons, d.pending_inputs) == (el.ELIGIBLE, (), ())
    assert el.decide(outcomes(**{el.DUES: el.PASSED})).status == el.ELIGIBLE


def test_an_unavailable_input_leaves_the_candidate_pending_without_a_reason():
    d = el.decide(outcomes(**{el.ATTENDANCE: el.UNAVAILABLE, el.DUES: el.UNAVAILABLE}))
    assert d.status == el.PENDING and d.reasons == ()
    assert d.pending_inputs == (el.ATTENDANCE, el.DUES)  # in FR-7's order


def test_a_failed_input_makes_the_candidate_ineligible_with_a_reason_each_in_order():
    d = el.decide(outcomes(**{el.ATTENDANCE: el.FAILED, el.REGISTRATION: el.FAILED}))
    assert d.status == el.INELIGIBLE
    assert [r["code"] for r in d.reasons] == ["not_registered", "attendance_shortage"]
    assert all(r["detail"] for r in d.reasons)


def test_a_failure_wins_over_a_missing_input_but_the_missing_input_is_still_reported():
    d = el.decide(outcomes(**{el.DUES: el.FAILED, el.STUDENT_STATUS: el.UNAVAILABLE}))
    assert d.status == el.INELIGIBLE and [r["code"] for r in d.reasons] == ["dues_outstanding"]
    assert d.pending_inputs == (el.STUDENT_STATUS,)


def test_the_statuses_and_inputs_are_the_contracts():
    assert el.ELIGIBILITY_STATUSES == ("pending", "eligible", "ineligible")
    assert el.INPUTS == ("registration", "student_status", "attendance", "dues")
    assert set(el.REASON_CODE.values()) == {
        "not_registered",
        "student_status",
        "attendance_shortage",
        "dues_outstanding",
    }
