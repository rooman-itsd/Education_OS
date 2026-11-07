"""Rules of sports-facilities (docs/prd.md, contracts/openapi.yaml). Pure Python: no database, no HTTP.

- A usage window ends after it starts.
- Operating hours are weekly slots in the institution's local time; each slot closes after it opens, and slots of
  the same day do not overlap. No slots at all means the facility is open at all times.
- Utilisation covers inclusive local dates, at most 366 days. Hours open come from the weekly slots (24 hours a day
  with none); hours used are the time the facility was in use, so two groups using it at once count once."""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta, tzinfo

FACILITY_TYPES = ("ground", "court", "pool", "gym", "track", "hall", "range", "other")
STATUSES = ("operational", "limited", "closed", "under_maintenance")
INITIAL_STATUS = "operational"
PURPOSES = ("training", "competition", "physical_education", "recreation", "event", "maintenance")
MAX_PERIOD_DAYS = 366


class RuleViolationError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Slot:
    day_of_week: int  # 0 = Monday
    opens_at: str  # HH:MM, local time
    closes_at: str

    @property
    def minutes(self) -> int:
        return minutes_of(self.closes_at) - minutes_of(self.opens_at)


def minutes_of(hhmm: str) -> int:
    hours, minutes = hhmm.split(":")
    return int(hours) * 60 + int(minutes)


def check_window(used_from: datetime, used_to: datetime) -> None:
    if used_to <= used_from:
        raise RuleViolationError("invalid_window", "used_to must be after used_from")


def check_slots(slots: Sequence[Slot]) -> list[Slot]:
    """The slots sorted by day and opening time, or a violation."""
    ordered = sorted(slots, key=lambda s: (s.day_of_week, s.opens_at))
    for s in ordered:
        if s.minutes <= 0:
            raise RuleViolationError("invalid_slot", f"day {s.day_of_week}: closes_at must be after opens_at")
    for prev, nxt in zip(ordered, ordered[1:], strict=False):
        if prev.day_of_week == nxt.day_of_week and minutes_of(nxt.opens_at) < minutes_of(prev.closes_at):
            raise RuleViolationError("overlapping_slots", f"day {nxt.day_of_week}: slots overlap")
    return ordered


def check_period(start: date, end: date) -> None:
    if end < start:
        raise RuleViolationError("invalid_period", "to must not be before from")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        raise RuleViolationError("period_too_long", f"the period is at most {MAX_PERIOD_DAYS} days")


def local_bounds(start: date | None, end: date | None, tz: tzinfo) -> tuple[datetime | None, datetime | None]:
    """[start 00:00, the day after end 00:00) in the local time zone, as UTC instants."""

    def midnight(day: date) -> datetime:
        return datetime.combine(day, time.min, tzinfo=tz).astimezone(UTC)

    return (
        midnight(start) if start else None,
        midnight(end + timedelta(days=1)) if end else None,
    )


def hours_open(slots: Sequence[Slot], start: date, end: date) -> float:
    """Hours open over the inclusive local dates: the weekly slots of each day, or 24 hours a day with none."""
    days = (end - start).days + 1
    if not slots:
        return 24.0 * days
    per_weekday = [0] * 7
    for s in slots:
        per_weekday[s.day_of_week] += s.minutes
    total = sum(per_weekday[(start + timedelta(days=i)).weekday()] for i in range(days))
    return total / 60


def hours_in_use(windows: Iterable[tuple[datetime, datetime]], start: datetime, end: datetime) -> float:
    """Hours covered by the windows inside [start, end); overlapping windows count once."""
    clipped = sorted((max(a, start), min(b, end)) for a, b in windows if a < end and b > start)
    total = timedelta()
    current: tuple[datetime, datetime] | None = None
    for a, b in clipped:
        if current and a <= current[1]:
            current = (current[0], max(current[1], b))
            continue
        if current:
            total += current[1] - current[0]
        current = (a, b)
    if current:
        total += current[1] - current[0]
    return total.total_seconds() / 3600
