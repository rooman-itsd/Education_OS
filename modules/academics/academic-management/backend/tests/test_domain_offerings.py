"""Unit tests of the offering and section rules (domain layer): FR-8 sections at creation, FR-9 status
transitions, FR-10 adding sections, and FR-12 one primary to open."""

import pytest
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.offerings import (
    CANCELLED,
    COMPLETED,
    IN_PROGRESS,
    OFFERING_STATUSES,
    OPEN,
    PLANNED,
    SECTION_CLOSED,
    TRANSITIONS,
    ensure_sections_can_be_added,
    ensure_transition,
    validate_new_offering,
    validate_section,
)


def error_of(fn):
    with pytest.raises(DomainRuleError) as err:
        fn()
    return (err.value.code, err.value.kind, err.value.field)


# --- sections


def test_section_needs_a_capacity_of_at_least_one():
    assert validate_section(capacity=1).capacity == 1
    assert validate_section(capacity=60, status=SECTION_CLOSED).status == SECTION_CLOSED


@pytest.mark.parametrize(
    ("kwargs", "code", "field"),
    [
        ({"capacity": 0}, "below_minimum", "capacity"),
        ({"capacity": 30.0}, "invalid_integer", "capacity"),
        ({"capacity": True}, "invalid_integer", "capacity"),
        ({"capacity": 30, "status": "full"}, "invalid_choice", "status"),
    ],
)
def test_invalid_sections(kwargs, code, field):
    assert error_of(lambda: validate_section(**kwargs)) == (code, "invalid", field)


# --- creating an offering


def test_offering_keeps_every_section():
    sections = validate_new_offering(course_status="active", section_capacities=[60, 40])
    assert [s.capacity for s in sections] == [60, 40]


def test_offering_needs_at_least_one_section():
    assert error_of(lambda: validate_new_offering(course_status="active", section_capacities=[])) == (
        "sections_required",
        "invalid",
        "sections",
    )


def test_invalid_section_names_its_position():
    assert error_of(lambda: validate_new_offering(course_status="active", section_capacities=[60, 0])) == (
        "below_minimum",
        "invalid",
        "sections[1].capacity",
    )


def test_archived_course_cannot_be_offered():
    assert error_of(lambda: validate_new_offering(course_status="archived", section_capacities=[60])) == (
        "course_archived",
        "conflict",
        None,
    )


def test_offering_rejects_an_unknown_course_status():
    assert error_of(lambda: validate_new_offering(course_status="deleted", section_capacities=[60]))[0] == (
        "invalid_choice"
    )


# --- adding sections


@pytest.mark.parametrize("status", [PLANNED, OPEN])
def test_sections_can_be_added_while_planned_or_open(status):
    ensure_sections_can_be_added(status)


@pytest.mark.parametrize("status", [IN_PROGRESS, COMPLETED, CANCELLED])
def test_sections_cannot_be_added_later(status):
    assert error_of(lambda: ensure_sections_can_be_added(status)) == ("offering_not_editable", "conflict", None)


# --- status transitions


@pytest.mark.parametrize(
    ("current", "target"),
    [(PLANNED, OPEN), (OPEN, IN_PROGRESS), (IN_PROGRESS, COMPLETED), (PLANNED, CANCELLED), (OPEN, CANCELLED)],
)
def test_contract_transitions_are_allowed(current, target):
    assert ensure_transition(current, target, active_primaries=1) == target


def test_exactly_the_contract_transitions_are_allowed():
    allowed = {(c, t) for c, targets in TRANSITIONS.items() for t in targets}
    assert allowed == {
        (PLANNED, OPEN),
        (OPEN, IN_PROGRESS),
        (IN_PROGRESS, COMPLETED),
        (PLANNED, CANCELLED),
        (OPEN, CANCELLED),
    }
    assert set(TRANSITIONS) == set(OFFERING_STATUSES)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        (PLANNED, IN_PROGRESS),
        (PLANNED, COMPLETED),
        (OPEN, PLANNED),
        (OPEN, OPEN),
        (IN_PROGRESS, CANCELLED),
        (COMPLETED, OPEN),
        (CANCELLED, PLANNED),
    ],
)
def test_other_transitions_are_a_conflict(current, target):
    assert error_of(lambda: ensure_transition(current, target, active_primaries=1)) == (
        "invalid_status_transition",
        "conflict",
        None,
    )


@pytest.mark.parametrize("primaries", [0, 2])
def test_opening_needs_exactly_one_primary(primaries):
    assert error_of(lambda: ensure_transition(PLANNED, OPEN, active_primaries=primaries)) == (
        "primary_required",
        "conflict",
        None,
    )


def test_cancelling_does_not_need_a_primary():
    assert ensure_transition(PLANNED, CANCELLED, active_primaries=0) == CANCELLED


@pytest.mark.parametrize(("current", "target"), [("closed", OPEN), (PLANNED, "archived"), (PLANNED, None)])
def test_unknown_statuses_are_invalid(current, target):
    assert error_of(lambda: ensure_transition(current, target, active_primaries=1))[:2] == (
        "invalid_choice",
        "invalid",
    )
