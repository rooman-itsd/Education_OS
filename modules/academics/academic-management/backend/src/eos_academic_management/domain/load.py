"""Faculty teaching load (contract `FacultyLoad`; PRD FR-13)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from .assignments import ACTIVE, ASSIGNMENT_STATUSES
from .values import require_choice, require_number


@dataclass(frozen=True)
class LoadEntry:
    """One assignment of one term, as the load query reads it."""

    faculty_id: str
    course_offering_id: str
    contact_hours: Decimal
    status: str


@dataclass(frozen=True)
class FacultyLoad:
    faculty_id: str
    offerings_count: int
    contact_hours: Decimal
    over_load: bool


def faculty_load(entries: Iterable[LoadEntry], *, max_weekly_contact_hours: object) -> list[FacultyLoad]:
    """FR-13: a faculty member's load for a term is the sum of the contact hours of their active assignments,
    compared to the organisation's maximum (ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS, read by the caller).
    Over the maximum is allowed but flagged; exactly at the maximum is not over it. The caller passes the
    entries of one term; whether assignments of cancelled offerings count is the caller's filter (the PRD does
    not say). Sorted by faculty_id so the result is stable."""
    maximum = require_number(max_weekly_contact_hours, "max_weekly_contact_hours", minimum=0)
    hours: dict[str, Decimal] = {}
    offerings: dict[str, set[str]] = {}
    for entry in entries:
        if require_choice(entry.status, "status", ASSIGNMENT_STATUSES) != ACTIVE:
            continue
        contact = require_number(entry.contact_hours, "contact_hours", minimum=0)
        hours[entry.faculty_id] = hours.get(entry.faculty_id, Decimal(0)) + contact
        offerings.setdefault(entry.faculty_id, set()).add(entry.course_offering_id)
    return [
        FacultyLoad(
            faculty_id=faculty_id,
            offerings_count=len(offerings[faculty_id]),
            contact_hours=total,
            over_load=total > maximum,
        )
        for faculty_id, total in sorted(hours.items())
    ]
