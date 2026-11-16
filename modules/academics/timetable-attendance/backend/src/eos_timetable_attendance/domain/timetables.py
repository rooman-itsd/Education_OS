"""Timetables and their slots (contract `Timetable`, `TimetableSlot`; PRD 5.1, FR-1, FR-2, FR-3)."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace
from datetime import date, time

from .errors import DomainRuleError
from .values import DAYS_OF_WEEK, optional_label, require_choice, require_date, require_id, require_time

DRAFT, PUBLISHED, UNPUBLISHED = "draft", "published", "unpublished"
TIMETABLE_STATUSES = (DRAFT, PUBLISHED, UNPUBLISHED)  # contract TimetableStatus
EDITABLE = (DRAFT, UNPUBLISHED)


@dataclass(frozen=True)
class Slot:
    """One recurring weekly slot. `effective_from` / `effective_to` (inclusive, optional) narrow the dates on which it
    applies; a missing bound leaves that side open to the range classes are generated for."""

    id: str
    day_of_week: str
    start_time: time
    end_time: time
    course_offering_id: str
    section_id: str
    instructor_assignment_id: str
    location_label: str | None = None
    effective_from: date | None = None
    effective_to: date | None = None

    def __post_init__(self) -> None:
        require_id(self.id, "id")
        require_choice(self.day_of_week, "day_of_week", DAYS_OF_WEEK)
        require_time(self.start_time, "start_time")
        require_time(self.end_time, "end_time")
        if self.end_time <= self.start_time:
            raise DomainRuleError(
                "invalid_slot_times", "end_time must be after start_time", kind="invalid", field="end_time"
            )
        require_id(self.course_offering_id, "course_offering_id")
        require_id(self.section_id, "section_id")
        require_id(self.instructor_assignment_id, "instructor_assignment_id")
        if (
            self.location_label is not None
            and optional_label(self.location_label, "location_label") != self.location_label
        ):
            raise DomainRuleError(
                "invalid_text", "location_label must be trimmed and not blank", kind="invalid", field="location_label"
            )
        if self.effective_from is not None:
            require_date(self.effective_from, "effective_from")
        if self.effective_to is not None:
            require_date(self.effective_to, "effective_to")
        if self.effective_from and self.effective_to and self.effective_to < self.effective_from:
            raise DomainRuleError(
                "invalid_effective_dates",
                "effective_to must not be before effective_from",
                kind="invalid",
                field="effective_to",
            )

    def dates_overlap(self, other: Slot) -> bool:
        """Whether the two slots can fall on a common date: open bounds overlap everything on that side."""
        starts = max((d for d in (self.effective_from, other.effective_from) if d), default=None)
        ends = min((d for d in (self.effective_to, other.effective_to) if d), default=None)
        return starts is None or ends is None or starts <= ends

    def times_overlap(self, other: Slot) -> tuple[time, time] | None:
        """The shared time of day on the same weekday, or None. Back-to-back slots do not overlap."""
        if self.day_of_week != other.day_of_week:
            return None
        start, end = max(self.start_time, other.start_time), min(self.end_time, other.end_time)
        return (start, end) if start < end else None


def new_slot(id_: str, data: dict) -> Slot:
    """A slot from a contract `TimetableSlotInput`; the location is trimmed and blank means none."""
    return Slot(
        id=id_,
        day_of_week=data.get("day_of_week"),
        start_time=data.get("start_time"),
        end_time=data.get("end_time"),
        course_offering_id=data.get("course_offering_id"),
        section_id=data.get("section_id"),
        instructor_assignment_id=data.get("instructor_assignment_id"),
        location_label=optional_label(data.get("location_label"), "location_label"),
        effective_from=data.get("effective_from"),
        effective_to=data.get("effective_to"),
    )


@dataclass(frozen=True)
class Timetable:
    id: str
    academic_period_id: str
    name: str
    department_id: str | None = None
    version: int = 0
    status: str = DRAFT

    def __post_init__(self) -> None:
        require_id(self.academic_period_id, "academic_period_id")
        if self.department_id is not None:
            require_id(self.department_id, "department_id")
        if not isinstance(self.name, str) or not self.name.strip() or len(self.name.strip()) > 200:
            raise DomainRuleError("invalid_name", "name must be 1 to 200 characters", kind="invalid", field="name")
        require_choice(self.status, "status", TIMETABLE_STATUSES)
        if isinstance(self.version, bool) or not isinstance(self.version, int) or self.version < 0:
            raise DomainRuleError("invalid_version", "version must be 0 or more", kind="invalid", field="version")


def ensure_editable(timetable: Timetable) -> None:
    """FR-2: a published timetable cannot be edited; unpublish it first."""
    if timetable.status not in EDITABLE:
        raise DomainRuleError(
            "timetable_published", "a published timetable cannot be edited; unpublish it first", kind="conflict"
        )


def ensure_unique_slots(slots: Iterable[Slot]) -> None:
    """A slot id appears once in a timetable's slot list."""
    seen: set[str] = set()
    for slot in slots:
        if slot.id in seen:
            raise DomainRuleError("duplicate_slot", f"slot {slot.id} is listed twice", kind="invalid", field="slots")
        seen.add(slot.id)


def ensure_known_references(
    slots: Iterable[Slot],
    *,
    offerings: set[str],
    sections: dict[str, str],
    assignments: dict[str, tuple[str, str | None]],
) -> None:
    """The slot IDs of academic-management must exist in the local read models (contract replaceTimetableSlots: 422).

    `sections` maps a known section id to its course offering id; `assignments` maps a known instructor assignment
    id to (course offering id, section id or None for an assignment to the whole offering). A slot's section must
    belong to its offering, and its assignment to the same offering and, when it names one, the same section."""
    for slot in slots:
        if slot.course_offering_id not in offerings:
            raise DomainRuleError(
                "unknown_course_offering",
                f"course offering {slot.course_offering_id} is not known",
                kind="unprocessable",
                field="course_offering_id",
            )
        if slot.section_id not in sections:
            raise DomainRuleError(
                "unknown_section", f"section {slot.section_id} is not known", kind="unprocessable", field="section_id"
            )
        if sections[slot.section_id] != slot.course_offering_id:
            raise DomainRuleError(
                "section_not_in_offering",
                f"section {slot.section_id} does not belong to course offering {slot.course_offering_id}",
                kind="unprocessable",
                field="section_id",
            )
        if slot.instructor_assignment_id not in assignments:
            raise DomainRuleError(
                "unknown_instructor_assignment",
                f"instructor assignment {slot.instructor_assignment_id} is not known",
                kind="unprocessable",
                field="instructor_assignment_id",
            )
        offering_id, section_id = assignments[slot.instructor_assignment_id]
        if offering_id != slot.course_offering_id or (section_id is not None and section_id != slot.section_id):
            raise DomainRuleError(
                "assignment_mismatch",
                f"instructor assignment {slot.instructor_assignment_id} is not for this course offering and section",
                kind="unprocessable",
                field="instructor_assignment_id",
            )


def ensure_offerings_in_period(
    slots: Iterable[Slot], offering_periods: dict[str, str], academic_period_id: str
) -> None:
    """A timetable plans one academic period, so every slot's course offering must be an offering of that period.
    `offering_periods` maps a known course offering id to its academic period id (from the local read model); offerings
    it does not hold are the business of `ensure_known_references`."""
    for slot in slots:
        period = offering_periods.get(slot.course_offering_id)
        if period is not None and period != academic_period_id:
            raise DomainRuleError(
                "offering_not_in_period",
                f"course offering {slot.course_offering_id} belongs to another academic period",
                kind="unprocessable",
                field="course_offering_id",
            )


@dataclass(frozen=True)
class Publication:
    """What publishing or unpublishing changes: the timetable as it becomes."""

    timetable: Timetable


def plan_publish(timetable: Timetable, *, blocking_conflicts: int) -> Publication:
    """FR-3: publish a draft or unpublished timetable that has no blocking conflict. The version goes up by one each
    time, so an unpublished timetable that is published again is a new version."""
    if timetable.status == PUBLISHED:
        raise DomainRuleError("already_published", "the timetable is already published", kind="conflict")
    if blocking_conflicts:
        raise DomainRuleError(
            "blocking_conflicts",
            f"{blocking_conflicts} blocking conflict(s) must be resolved before publishing",
            kind="conflict",
            details={"blocking_conflicts": blocking_conflicts},
        )
    return Publication(replace(timetable, status=PUBLISHED, version=timetable.version + 1))


def ensure_known_term(timetable: Timetable, *, term_known: bool) -> None:
    """Reviewer decision (docs/reviewer-decisions.md, section 2): a timetable is published only when its academic
    period is a term the module knows (its `term_ref`, from `academic-management.term.created`), because the term's
    dates bound the classes that publishing generates."""
    if not term_known:
        raise DomainRuleError(
            "unknown_term",
            f"academic period {timetable.academic_period_id} is not a known term, so the timetable cannot be published",
            kind="conflict",
            details={"academic_period_id": timetable.academic_period_id},
        )


def plan_unpublish(timetable: Timetable) -> Publication:
    """FR-3: only a published timetable can be unpublished. Its version stays; the next publication raises it."""
    if timetable.status != PUBLISHED:
        raise DomainRuleError("not_published", "only a published timetable can be unpublished", kind="conflict")
    return Publication(replace(timetable, status=UNPUBLISHED))
