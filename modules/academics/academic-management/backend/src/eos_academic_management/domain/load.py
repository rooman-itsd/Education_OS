"""Faculty teaching load (contract `FacultyLoad`, `FacultyLoadReport`; PRD FR-13)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from .assignments import ACTIVE, ASSIGNMENT_STATUSES, CO_INSTRUCTOR, FACULTY_ROLES, PRIMARY
from .values import require_choice, require_number

# Owner decision on PR #168 (v1): teaching-assistant hours do not count towards faculty load.
COUNTED_ROLES = (PRIMARY, CO_INSTRUCTOR)


@dataclass(frozen=True)
class LoadEntry:
    """One assignment of one term, as the load query reads it."""

    faculty_id: str
    course_offering_id: str
    role: str
    contact_hours: Decimal
    status: str


@dataclass(frozen=True)
class FacultyLoad:
    faculty_id: str
    offerings_count: int
    contact_hours: Decimal
    over_load: bool


@dataclass(frozen=True)
class LoadSummary:
    """The rows of a load report and the counts the contract keeps independent of `over_load_only`."""

    items: tuple[FacultyLoad, ...]
    faculty_count: int
    over_load_count: int


def faculty_load(entries: Iterable[LoadEntry], *, max_weekly_contact_hours: object) -> list[FacultyLoad]:
    """FR-13: a faculty member's load for a term is the sum of the contact hours of their active primary and
    co-instructor assignments, compared to the organisation's maximum (ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS,
    read by the caller). Over the maximum is allowed but flagged; exactly at the maximum is not over it.

    Owner decisions on PR #168 (v1): teaching-assistant assignments do not count, and a faculty member with no
    counted assignment is not listed. Rows are ordered over-load first, then by contact hours descending; ties
    fall back to faculty_id so the order is stable.

    The caller passes the entries of one term; whether assignments of cancelled offerings count is the caller's
    filter (the PRD does not say)."""
    maximum = require_number(max_weekly_contact_hours, "max_weekly_contact_hours", minimum=0)
    hours: dict[str, Decimal] = {}
    offerings: dict[str, set[str]] = {}
    for entry in entries:
        role = require_choice(entry.role, "role", FACULTY_ROLES)
        if require_choice(entry.status, "status", ASSIGNMENT_STATUSES) != ACTIVE or role not in COUNTED_ROLES:
            continue
        contact = require_number(entry.contact_hours, "contact_hours", minimum=0)
        hours[entry.faculty_id] = hours.get(entry.faculty_id, Decimal(0)) + contact
        offerings.setdefault(entry.faculty_id, set()).add(entry.course_offering_id)
    loads = [
        FacultyLoad(
            faculty_id=faculty_id,
            offerings_count=len(offerings[faculty_id]),
            contact_hours=total,
            over_load=total > maximum,
        )
        for faculty_id, total in hours.items()
    ]
    return sorted(loads, key=lambda load: (not load.over_load, -load.contact_hours, load.faculty_id))


def summarise(loads: Iterable[FacultyLoad], *, over_load_only: bool = False) -> LoadSummary:
    """GET /faculty-load: `faculty_count` and `over_load_count` describe every listed faculty member, and stay the
    same when `over_load_only` narrows the rows (owner decision on PR #168). The order of `loads` is kept."""
    loads = tuple(loads)
    over = tuple(load for load in loads if load.over_load)
    return LoadSummary(
        items=over if over_load_only else loads,
        faculty_count=len(loads),
        over_load_count=len(over),
    )
