"""Course offerings and their sections (contract `CourseOffering`, `Section`; PRD FR-8, FR-9, FR-10)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from .courses import ARCHIVED as COURSE_ARCHIVED
from .courses import COURSE_STATUSES
from .errors import DomainRuleError
from .values import require_choice, require_integer

PLANNED, OPEN, IN_PROGRESS, COMPLETED, CANCELLED = "planned", "open", "in_progress", "completed", "cancelled"
OFFERING_STATUSES = (PLANNED, OPEN, IN_PROGRESS, COMPLETED, CANCELLED)  # contract OfferingStatus
SECTION_OPEN, SECTION_CLOSED = "open", "closed"
SECTION_STATUSES = (SECTION_OPEN, SECTION_CLOSED)  # contract SectionStatus

# changeOfferingStatus: "planned→open, open→in_progress, in_progress→completed, and planned|open→cancelled".
TRANSITIONS: dict[str, tuple[str, ...]] = {
    PLANNED: (OPEN, CANCELLED),
    OPEN: (IN_PROGRESS, CANCELLED),
    IN_PROGRESS: (COMPLETED,),
    COMPLETED: (),
    CANCELLED: (),
}
# FR-12 "open or later": the states reached through open. cancelled is not one of them, since a planned offering
# can be cancelled without ever opening.
STAFFED_STATUSES = (OPEN, IN_PROGRESS, COMPLETED)
# FR-10: sections can be added while an offering is planned or open.
SECTION_EDITABLE_STATUSES = (PLANNED, OPEN)


@dataclass(frozen=True)
class SectionShape:
    """The validated, rule-bearing fields of a section. code is carried unchanged."""

    capacity: int
    status: str = SECTION_OPEN


def validate_section(*, capacity: object, status: object = SECTION_OPEN) -> SectionShape:
    """Contract CreateSectionRequest and UpdateSectionRequest: capacity is an integer >= 1, status is a
    SectionStatus. Whether capacity may drop below the enrolled count is left to the enrolment contract (open
    question; no roster contract yet)."""
    return SectionShape(
        capacity=require_integer(capacity, "capacity", minimum=1),
        status=require_choice(status, "status", SECTION_STATUSES),
    )


def validate_new_offering(*, course_status: str, section_capacities: Iterable[object]) -> tuple[SectionShape, ...]:
    """FR-8 and contract CreateOfferingRequest: an offering has at least one section (minItems 1), each with a
    capacity. A course that is archived "can no longer be offered" (event course.archived), which createOffering
    answers with 409."""
    require_choice(course_status, "course_status", COURSE_STATUSES)
    if course_status == COURSE_ARCHIVED:
        raise DomainRuleError("course_archived", "an archived course cannot be offered", kind="conflict")
    sections = []
    for index, capacity in enumerate(section_capacities):
        try:
            sections.append(validate_section(capacity=capacity))
        except DomainRuleError as err:
            raise DomainRuleError(
                err.code, f"section {index}: {err.message}", kind="invalid", field=f"sections[{index}].{err.field}"
            ) from err
    if not sections:
        raise DomainRuleError(
            "sections_required", "an offering needs at least one section", kind="invalid", field="sections"
        )
    return tuple(sections)


def ensure_sections_can_be_added(offering_status: str) -> None:
    """FR-10: sections are added only while the offering is planned or open (createSection answers 409)."""
    require_choice(offering_status, "status", OFFERING_STATUSES)
    if offering_status not in SECTION_EDITABLE_STATUSES:
        raise DomainRuleError(
            "offering_not_editable",
            f"sections cannot be added to a {offering_status} offering",
            kind="conflict",
        )


def ensure_transition(current: str, target: object, *, active_primaries: int) -> str:
    """FR-9 and changeOfferingStatus: only the listed transitions are allowed (409 otherwise). "Moving to open
    requires exactly one primary faculty assignment" (FR-12); `active_primaries` is the number of active
    assignments with role primary, counted by assignments.count_active_primaries."""
    require_choice(current, "status", OFFERING_STATUSES)
    target = require_choice(target, "status", OFFERING_STATUSES)
    if target not in TRANSITIONS[current]:
        raise DomainRuleError(
            "invalid_status_transition", f"an offering cannot move from {current} to {target}", kind="conflict"
        )
    active_primaries = require_integer(active_primaries, "active_primaries", minimum=0)
    if target == OPEN and active_primaries != 1:
        raise DomainRuleError(
            "primary_required",
            f"opening an offering needs exactly one primary faculty assignment, found {active_primaries}",
            kind="conflict",
        )
    return target
