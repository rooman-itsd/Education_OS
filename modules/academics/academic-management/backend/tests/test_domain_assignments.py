"""Unit tests of the faculty assignment rules (domain layer): FR-11 and FR-12 one primary once open."""

from decimal import Decimal

import pytest
from eos_academic_management.domain.assignments import (
    CO_INSTRUCTOR,
    ENDED,
    FACULTY_ROLES,
    PRIMARY,
    TEACHING_ASSISTANT,
    Assignment,
    count_active_primaries,
    ensure_can_end,
    validate_assignment,
)
from eos_academic_management.domain.errors import DomainRuleError
from eos_academic_management.domain.offerings import CANCELLED, COMPLETED, IN_PROGRESS, OPEN, PLANNED

LEAD = Assignment("a1", "f1", None, PRIMARY, Decimal(4))
TA = Assignment("a2", "f2", "s1", TEACHING_ASSISTANT, Decimal(2))
FORMER_LEAD = Assignment("a0", "f0", None, PRIMARY, Decimal(4), ENDED)


def assign(**kwargs):
    values = {
        "faculty_id": "f9",
        "role": CO_INSTRUCTOR,
        "contact_hours": 3,
        "section_id": None,
        "offering_section_ids": ["s1", "s2"],
        "offering_status": PLANNED,
        "existing": [],
        **kwargs,
    }
    return validate_assignment(**values)


def error_of(fn):
    with pytest.raises(DomainRuleError) as err:
        fn()
    return (err.value.code, err.value.kind, err.value.field)


# --- creating


@pytest.mark.parametrize("role", FACULTY_ROLES)
def test_every_contract_role_is_accepted(role):
    assert assign(role=role).role == role


def test_assignment_to_the_whole_offering_or_one_of_its_sections():
    assert assign().section_id is None
    made = assign(section_id="s2", contact_hours=Decimal("1.5"))
    assert (made.section_id, made.contact_hours, made.status) == ("s2", Decimal("1.5"), "active")


def test_contact_hours_may_be_zero():
    assert assign(contact_hours=0).contact_hours == Decimal(0)


@pytest.mark.parametrize(
    ("kwargs", "code", "field"),
    [
        ({"faculty_id": ""}, "invalid_faculty", "faculty_id"),
        ({"faculty_id": None}, "invalid_faculty", "faculty_id"),
        ({"role": "lecturer"}, "invalid_choice", "role"),
        ({"contact_hours": -1}, "below_minimum", "contact_hours"),
        ({"contact_hours": float("nan")}, "invalid_number", "contact_hours"),
        ({"section_id": "s9"}, "section_not_in_offering", "section_id"),
        ({"offering_status": "archived"}, "invalid_choice", "status"),
    ],
)
def test_invalid_assignments(kwargs, code, field):
    assert error_of(lambda: assign(**kwargs)) == (code, "invalid", field)


@pytest.mark.parametrize("status", [OPEN, IN_PROGRESS, COMPLETED])
def test_second_primary_of_an_open_or_later_offering_is_a_conflict(status):
    assert error_of(lambda: assign(role=PRIMARY, offering_status=status, existing=[LEAD, TA])) == (
        "primary_already_assigned",
        "conflict",
        "role",
    )


def test_an_ended_primary_does_not_block_a_new_one():
    assert assign(role=PRIMARY, offering_status=OPEN, existing=[FORMER_LEAD, TA]).role == PRIMARY


def test_other_roles_can_be_added_to_an_open_offering():
    assert assign(role=CO_INSTRUCTOR, offering_status=OPEN, existing=[LEAD]).role == CO_INSTRUCTOR


@pytest.mark.parametrize("status", [PLANNED, CANCELLED])
def test_second_primary_before_opening_is_not_refused_open_question(status):
    # FR-12 applies from open on; opening then needs exactly one active primary (ensure_transition).
    assert assign(role=PRIMARY, offering_status=status, existing=[LEAD]).role == PRIMARY


def test_counting_primaries_ignores_ended_and_other_roles():
    assert count_active_primaries([LEAD, TA, FORMER_LEAD]) == 1
    assert count_active_primaries([]) == 0


# --- ending


def test_ending_an_active_assignment():
    assert ensure_can_end(TA, offering_status=OPEN) == ENDED
    assert ensure_can_end(LEAD, offering_status=PLANNED) == ENDED
    assert ensure_can_end(LEAD, offering_status=CANCELLED) == ENDED


def test_ending_twice_is_a_conflict():
    assert error_of(lambda: ensure_can_end(FORMER_LEAD, offering_status=PLANNED)) == (
        "assignment_ended",
        "conflict",
        None,
    )


@pytest.mark.parametrize("status", [OPEN, IN_PROGRESS, COMPLETED])
def test_primary_of_an_open_or_later_offering_cannot_be_ended(status):
    assert error_of(lambda: ensure_can_end(LEAD, offering_status=status)) == ("primary_required", "conflict", None)


def test_ending_rejects_unknown_statuses():
    bad = Assignment("a3", "f3", None, CO_INSTRUCTOR, Decimal(1), "paused")
    assert error_of(lambda: ensure_can_end(bad, offering_status=OPEN))[0] == "invalid_choice"
    assert error_of(lambda: ensure_can_end(TA, offering_status="archived"))[0] == "invalid_choice"
