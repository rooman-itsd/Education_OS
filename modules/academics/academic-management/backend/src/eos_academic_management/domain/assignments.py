"""Faculty assignments (contract `FacultyAssignment`; PRD FR-11, FR-12).

faculty_id is the contract's field, described there as a platform/identity user id. Which staff identifier the
module stores is decision A (pending with Faizan); the domain treats it as an opaque string."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from .errors import DomainRuleError
from .offerings import OFFERING_STATUSES, STAFFED_STATUSES
from .values import require_choice, require_number

PRIMARY, CO_INSTRUCTOR, TEACHING_ASSISTANT = "primary", "co_instructor", "teaching_assistant"
FACULTY_ROLES = (PRIMARY, CO_INSTRUCTOR, TEACHING_ASSISTANT)  # contract FacultyRole
ACTIVE, ENDED = "active", "ended"
ASSIGNMENT_STATUSES = (ACTIVE, ENDED)  # contract AssignmentStatus


@dataclass(frozen=True)
class Assignment:
    id: str
    faculty_id: str
    section_id: str | None  # None means the whole offering
    role: str
    contact_hours: Decimal
    status: str = ACTIVE


def count_active_primaries(assignments: Iterable[Assignment]) -> int:
    """The number of active primary assignments of one offering."""
    return sum(1 for a in assignments if a.role == PRIMARY and a.status == ACTIVE)


def validate_assignment(
    *,
    faculty_id: object,
    role: object,
    contact_hours: object,
    section_id: str | None,
    offering_section_ids: Iterable[str],
    offering_status: str,
    existing: Iterable[Assignment],
) -> Assignment:
    """FR-11 and contract CreateFacultyAssignmentRequest: role is a FacultyRole, contact_hours >= 0, and a
    section, when given, is one of the offering's sections. FR-12: an offering in open or later state keeps
    exactly one primary, so a second active primary is a conflict (409). The returned assignment has no id yet.

    Not decided by the PRD or the contract, so not enforced here: a second primary while the offering is still
    planned (opening then fails until one is ended), the same faculty member assigned twice, and assignments
    to a completed or cancelled offering."""
    if not isinstance(faculty_id, str) or not faculty_id:
        raise DomainRuleError("invalid_faculty", "faculty_id is required", kind="invalid", field="faculty_id")
    role = require_choice(role, "role", FACULTY_ROLES)
    hours = require_number(contact_hours, "contact_hours", minimum=0)
    if section_id is not None and section_id not in set(offering_section_ids):
        raise DomainRuleError(
            "section_not_in_offering",
            "the section does not belong to this offering",
            kind="invalid",
            field="section_id",
        )
    require_choice(offering_status, "status", OFFERING_STATUSES)
    if role == PRIMARY and offering_status in STAFFED_STATUSES and count_active_primaries(existing) >= 1:
        raise DomainRuleError(
            "primary_already_assigned",
            f"a {offering_status} offering already has its primary faculty",
            kind="conflict",
            field="role",
        )
    return Assignment(id="", faculty_id=faculty_id, section_id=section_id, role=role, contact_hours=hours)


def ensure_can_end(assignment: Assignment, *, offering_status: str) -> str:
    """POST /faculty-assignments/{id}/end (endFacultyAssignment answers 409). Ending an ended assignment is a
    conflict. FR-12: the primary of an offering in open or later state cannot be ended, since the offering
    would be left without one. The contract has no operation to replace a primary in one step, so how a
    primary is changed once the offering is open is an open question."""
    require_choice(assignment.status, "status", ASSIGNMENT_STATUSES)
    require_choice(offering_status, "status", OFFERING_STATUSES)
    if assignment.status == ENDED:
        raise DomainRuleError("assignment_ended", "this assignment has already ended", kind="conflict")
    if assignment.role == PRIMARY and offering_status in STAFFED_STATUSES:
        raise DomainRuleError(
            "primary_required",
            f"the primary faculty of a {offering_status} offering cannot be removed",
            kind="conflict",
        )
    return ENDED
