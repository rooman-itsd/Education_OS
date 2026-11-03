"""Scheduled classes (contract `ScheduledClass`; PRD 5.2, FR-5): generation from slots, ad-hoc classes, rescheduling
and cancelling."""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass, replace
from datetime import UTC, date, datetime, timedelta, tzinfo

from .errors import DomainRuleError
from .timetables import Slot
from .values import (
    optional_label,
    require_choice,
    require_date,
    require_id,
    require_instant,
    require_text,
    weekday_name,
)

SCHEDULED, CANCELLED, COMPLETED = "scheduled", "cancelled", "completed"
CLASS_STATUSES = (SCHEDULED, CANCELLED, COMPLETED)  # contract ScheduledClassStatus


@dataclass(frozen=True)
class ScheduledClass:
    id: str
    academic_period_id: str
    course_offering_id: str
    section_id: str
    instructor_assignment_id: str
    instructor_id: str
    class_date: date
    starts_at: datetime
    ends_at: datetime
    timetable_id: str | None = None
    slot_id: str | None = None
    location_label: str | None = None
    status: str = SCHEDULED
    cancel_reason: str | None = None

    def __post_init__(self) -> None:
        for field in ("id", "academic_period_id", "course_offering_id", "section_id", "instructor_assignment_id"):
            require_id(getattr(self, field), field)
        require_id(self.instructor_id, "instructor_id")
        require_date(self.class_date, "class_date")
        require_instant(self.starts_at, "starts_at")
        require_instant(self.ends_at, "ends_at")
        if self.ends_at <= self.starts_at:
            raise DomainRuleError(
                "invalid_class_times", "ends_at must be after starts_at", kind="invalid", field="ends_at"
            )
        require_choice(self.status, "status", CLASS_STATUSES)

    @property
    def is_adhoc(self) -> bool:
        return self.slot_id is None


def occurrence_window(class_date: date, slot: Slot, zone: tzinfo) -> tuple[datetime, datetime]:
    """The start and end of a slot on a date, as UTC instants, with the slot's wall-clock times read in the
    organisation's time zone."""
    start = datetime.combine(class_date, slot.start_time, tzinfo=zone).astimezone(UTC)
    end = datetime.combine(class_date, slot.end_time, tzinfo=zone).astimezone(UTC)
    return start, end


def slot_dates(slot: Slot, first: date, last: date) -> Iterator[date]:
    """FR-5: every date from `first` to `last` (inclusive) on the slot's weekday and inside its effective dates."""
    require_date(first, "from")
    require_date(last, "to")
    if last < first:
        raise DomainRuleError("invalid_range", "to must not be before from", kind="invalid", field="to")
    start = max(first, slot.effective_from) if slot.effective_from else first
    end = min(last, slot.effective_to) if slot.effective_to else last
    day = start
    while day <= end:
        if weekday_name(day) == slot.day_of_week:
            yield day
        day += timedelta(days=1)


def missing_occurrences(slot: Slot, first: date, last: date, existing_dates: Iterable[date]) -> list[date]:
    """FR-5, idempotent generation: the dates of the slot in the range that have no class yet (one class per slot and
    date). A cancelled class still occupies its date, so cancelling a generated class does not bring it back."""
    have = set(existing_dates)
    return [d for d in slot_dates(slot, first, last) if d not in have]


def new_adhoc_window(starts_at: object, ends_at: object) -> tuple[datetime, datetime]:
    """An ad-hoc class (extra or make-up): both moments carry a zone and the class ends after it starts."""
    start, end = require_instant(starts_at, "starts_at"), require_instant(ends_at, "ends_at")
    if end <= start:
        raise DomainRuleError("invalid_class_times", "ends_at must be after starts_at", kind="invalid", field="ends_at")
    return start, end


def ensure_changeable(cls: ScheduledClass, *, has_closed_session: bool) -> None:
    """A class can be rescheduled or cancelled while it is scheduled and has no closed attendance session (FR-5)."""
    if cls.status == CANCELLED:
        raise DomainRuleError("class_cancelled", "the class is cancelled", kind="conflict")
    if cls.status == COMPLETED or has_closed_session:
        raise DomainRuleError(
            "attendance_closed", "the class has a closed attendance session and can no longer change", kind="conflict"
        )


def plan_reschedule(
    cls: ScheduledClass,
    *,
    has_closed_session: bool,
    starts_at: object | None = None,
    ends_at: object | None = None,
    zone: tzinfo = UTC,
    location_label: object = ...,
    instructor: tuple[str, str] | None = None,
) -> tuple[ScheduledClass, list[str]]:
    """Reschedule a class or change its location or instructor assignment. The class keeps its id.

    `instructor` is (instructor assignment id, instructor id) of the new assignment, resolved by the caller from the
    local read model. Returns the class as it becomes and the names of the fields that changed (the event's
    `changed_fields`). Giving only one of `starts_at` and `ends_at` moves that end; the result must still end after it
    starts. `class_date` follows `starts_at`, read in `zone`. A change that alters nothing returns no field names."""
    ensure_changeable(cls, has_closed_session=has_closed_session)
    changes: dict[str, object] = {}
    start = require_instant(starts_at, "starts_at") if starts_at is not None else cls.starts_at
    end = require_instant(ends_at, "ends_at") if ends_at is not None else cls.ends_at
    if end <= start:
        raise DomainRuleError("invalid_class_times", "ends_at must be after starts_at", kind="invalid", field="ends_at")
    if start != cls.starts_at:
        changes["starts_at"] = start
        changes["class_date"] = start.astimezone(zone).date()
    if end != cls.ends_at:
        changes["ends_at"] = end
    if location_label is not ...:
        label = optional_label(location_label, "location_label")
        if label != cls.location_label:
            changes["location_label"] = label
    if instructor is not None:
        assignment_id, instructor_id = (
            require_id(instructor[0], "instructor_assignment_id"),
            require_id(instructor[1], "instructor_id"),
        )
        if assignment_id != cls.instructor_assignment_id:
            changes["instructor_assignment_id"] = assignment_id
            changes["instructor_id"] = instructor_id
    if not changes:
        return cls, []
    changed = [k for k in changes if k not in ("class_date", "instructor_id")]
    return replace(cls, **changes), changed


def plan_cancel(cls: ScheduledClass, *, has_closed_session: bool, reason: object | None = None) -> ScheduledClass:
    """Cancel a class that has no closed attendance session. An open session is not a bar: the class is cancelled and
    attendance can no longer be marked (FR-7: marking needs a scheduled class)."""
    ensure_changeable(cls, has_closed_session=has_closed_session)
    text = None if reason is None else require_text(reason, "reason", max_length=500)
    return replace(cls, status=CANCELLED, cancel_reason=text)


def classes_to_cancel_on_unpublish(
    classes: Iterable[ScheduledClass], sessions_by_class: Iterable[str], now: datetime
) -> list[ScheduledClass]:
    """FR-3: unpublishing cancels the timetable's future scheduled classes that have no attendance session. Past
    classes, classes that already started, completed or cancelled classes, and every class with a session (open or
    closed) are never touched. `sessions_by_class` holds the ids of classes that have a session."""
    with_session = set(sessions_by_class)
    now = require_instant(now, "now")
    return [c for c in classes if c.status == SCHEDULED and c.starts_at > now and c.id not in with_session]
