"""Booking rules, conflicts, recurrence and availability. Pure Python: no framework or database imports
(module standard, backend/src/domain). Every datetime here is timezone-aware."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timedelta, tzinfo

ACTIVE_STATUSES = frozenset({"pending", "confirmed", "checked_in"})  # these hold the slot (PRD rule 1)
CHANGEABLE_STATUSES = frozenset({"pending", "confirmed"})
RESOURCE_STATUSES = ("active", "inactive", "under_maintenance")
BOOKING_STATUSES = ("pending", "confirmed", "rejected", "cancelled", "checked_in", "completed", "no_show")
CHECK_IN_OPENS_BEFORE = timedelta(minutes=15)
DAY_MINUTES = 24 * 60


class RuleViolationError(Exception):
    """A booking rule, the opening hours or a closure forbids this window (HTTP 422, contract RuleError)."""

    def __init__(self, code: str, message: str, rule: str | None = None, limit: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.rule = rule
        self.limit = limit


@dataclass(frozen=True)
class Rules:
    """Contract BookingRules after falling back resource → resource type → organisation default."""

    requires_approval: bool = False
    check_in_required: bool = False
    min_duration_minutes: int | None = None
    max_duration_minutes: int | None = None
    slot_minutes: int = 30
    max_days_ahead: int = 90
    buffer_minutes: int = 0
    max_concurrent_bookings: int = 1
    bookable_role_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bookable_role_ids"] = list(self.bookable_role_ids)
        return d


RULE_FIELDS = tuple(Rules.__dataclass_fields__)


def effective_rules(defaults: Rules, *layers: dict | None) -> Rules:
    """Later layers win; a missing or null value keeps the earlier one."""
    values = asdict(defaults)
    for layer in layers:
        for key, value in (layer or {}).items():
            if key in values and value is not None:
                values[key] = value
    values["bookable_role_ids"] = tuple(values["bookable_role_ids"] or ())
    return Rules(**values)


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime

    def overlaps(self, other: Window, pad: timedelta = timedelta(0)) -> bool:
        """True when the two windows overlap, keeping `pad` free between them."""
        return self.start < other.end + pad and other.start < self.end + pad

    @property
    def minutes(self) -> int:
        return int((self.end - self.start).total_seconds() // 60)


@dataclass(frozen=True)
class OpeningHours:
    weekday: int  # ISO, 1 = Monday
    opens: str  # "HH:MM" local
    closes: str  # "HH:MM" local, "24:00" allowed


def hhmm_to_minutes(value: str) -> int:
    hours, minutes = value.split(":")
    return int(hours) * 60 + int(minutes)


def _local_minutes(window: Window, tz: tzinfo) -> tuple[datetime, int, int]:
    """Local start, and start/end as minutes after the local midnight of the start day."""
    local_start = window.start.astimezone(tz)
    midnight = local_start.replace(hour=0, minute=0, second=0, microsecond=0)
    start_min = int((local_start - midnight).total_seconds() // 60)
    end_min = int((window.end.astimezone(tz) - midnight).total_seconds() // 60)
    return local_start, start_min, end_min


def check_window(
    window: Window,
    rules: Rules,
    *,
    now: datetime,
    opening: list[OpeningHours],
    blackouts: list[Window],
    tz: tzinfo,
) -> None:
    """Raise RuleViolationError if the window breaks a rule (PRD section 6, rules 2 and 3)."""
    if window.end <= window.start:
        raise RuleViolationError("invalid_window", "end must be after start")
    if window.start < now:
        raise RuleViolationError("in_the_past", "the booking would start in the past")
    if rules.min_duration_minutes and window.minutes < rules.min_duration_minutes:
        raise RuleViolationError(
            "too_short", "the booking is too short", "min_duration_minutes", rules.min_duration_minutes
        )
    if rules.max_duration_minutes and window.minutes > rules.max_duration_minutes:
        raise RuleViolationError(
            "too_long", "the booking is too long", "max_duration_minutes", rules.max_duration_minutes
        )
    if window.start > now + timedelta(days=rules.max_days_ahead):
        raise RuleViolationError(
            "too_far_ahead", "the booking is too far ahead", "max_days_ahead", rules.max_days_ahead
        )
    _, start_min, end_min = _local_minutes(window, tz)
    exact = window.start.second == 0 and window.start.microsecond == 0
    exact = exact and window.end.second == 0 and window.end.microsecond == 0
    if not exact or start_min % rules.slot_minutes or end_min % rules.slot_minutes:
        raise RuleViolationError(
            "misaligned_slot", "start and end must align to the slot grid", "slot_minutes", rules.slot_minutes
        )
    if opening and not is_within_opening_hours(window, opening, tz):
        raise RuleViolationError("outside_opening_hours", "the resource is closed for part of this window")
    for blackout in blackouts:
        if window.overlaps(blackout):
            raise RuleViolationError("in_blackout", "the resource is closed for this window")


def is_within_opening_hours(window: Window, opening: list[OpeningHours], tz: tzinfo) -> bool:
    if not opening:
        return True
    local_start, start_min, end_min = _local_minutes(window, tz)
    if end_min > DAY_MINUTES:
        return False
    weekday = local_start.isoweekday()
    return any(
        o.weekday == weekday and hhmm_to_minutes(o.opens) <= start_min and end_min <= hhmm_to_minutes(o.closes)
        for o in opening
    )


def peak_concurrency(windows: list[Window]) -> int:
    """Largest number of windows that overlap at one instant."""
    points = sorted([(w.start, 1) for w in windows] + [(w.end, -1) for w in windows], key=lambda p: (p[0], p[1]))
    running = peak = 0
    for _, delta in points:
        running += delta
        peak = max(peak, running)
    return peak


def find_conflicts(window: Window, existing: list[Window], *, buffer_minutes: int, max_concurrent: int) -> list[Window]:
    """Existing windows that stop this one from fitting. Empty means it fits (PRD rule 1)."""
    pad = timedelta(minutes=buffer_minutes)
    clashing = [w for w in existing if window.overlaps(w, pad)]
    if not clashing:
        return []
    if max_concurrent > 1:
        padded = [Window(max(w.start, window.start - pad), min(w.end + pad, window.end + pad)) for w in clashing]
        if peak_concurrency(padded) < max_concurrent:
            return []
    return clashing


def expand_recurrence(
    first: Window,
    *,
    frequency: str,
    interval: int = 1,
    weekdays: list[int] | None = None,
    until: date | None = None,
    count: int | None = None,
    limit: int,
    tz: tzinfo,
) -> list[Window]:
    """Occurrences of a daily or weekly series, starting with `first` (PRD rule 7). Wall-clock times stay
    the same in the organisation's time zone."""
    if (until is None) == (count is None):
        raise RuleViolationError("invalid_window", "give exactly one of until or count")
    if frequency not in ("daily", "weekly"):
        raise RuleViolationError("invalid_window", "frequency must be daily or weekly")
    duration = first.end - first.start
    local_first = first.start.astimezone(tz)
    occurrences: list[datetime] = []

    def full() -> bool:
        return count is not None and len(occurrences) >= count

    def add(candidate: datetime) -> bool:
        """Append; return False when the series is finished."""
        if until is not None and candidate.date() > until:
            return False
        occurrences.append(candidate)
        if len(occurrences) > limit:
            raise RuleViolationError(
                "too_many_occurrences", "the series has too many occurrences", "max_series_occurrences", limit
            )
        return not full()

    if frequency == "daily":
        current = local_first
        while add(current):
            current = _shift_days(current, interval, tz)
    else:
        days = sorted(set(weekdays or [local_first.isoweekday()]))
        week_monday = local_first.date() - timedelta(days=local_first.isoweekday() - 1)
        week = 0
        running = True
        while running:
            for day in days:
                day_date = week_monday + timedelta(weeks=week * interval, days=day - 1)
                candidate = datetime.combine(day_date, local_first.timetz().replace(tzinfo=None), tzinfo=tz)
                if candidate < local_first:
                    continue
                if not add(candidate):
                    running = False
                    break
            week += 1
    return [Window(start, start + duration) for start in occurrences]


def _shift_days(value: datetime, days: int, tz: tzinfo) -> datetime:
    naive = value.replace(tzinfo=None) + timedelta(days=days)
    return naive.replace(tzinfo=tz)


def closed_windows(span: Window, opening: list[OpeningHours], tz: tzinfo) -> list[Window]:
    """Parts of `span` outside the opening hours."""
    if not opening:
        return []
    closed: list[Window] = []
    day = span.start.astimezone(tz).date()
    last = span.end.astimezone(tz).date()
    while day <= last:
        midnight = datetime.combine(day, time(0), tzinfo=tz)
        open_today = sorted(
            (hhmm_to_minutes(o.opens), hhmm_to_minutes(o.closes)) for o in opening if o.weekday == day.isoweekday()
        )
        cursor = 0
        for opens, closes in [*open_today, (DAY_MINUTES, DAY_MINUTES)]:
            if opens > cursor:
                closed.append(Window(midnight + timedelta(minutes=cursor), midnight + timedelta(minutes=opens)))
            cursor = max(cursor, closes)
        day += timedelta(days=1)
    return [Window(max(w.start, span.start), min(w.end, span.end)) for w in closed if w.overlaps(span)]


def full_windows(bookings: list[Window], max_concurrent: int) -> list[Window]:
    """Intervals where bookings reach the concurrency limit."""
    if max_concurrent <= 1:
        return sorted(bookings, key=lambda w: w.start)
    points = sorted({p for w in bookings for p in (w.start, w.end)})
    full: list[Window] = []
    for a, b in zip(points, points[1:], strict=False):
        if sum(1 for w in bookings if w.start <= a and w.end >= b) >= max_concurrent:
            full.append(Window(a, b))
    return merge(full)


def merge(windows: list[Window]) -> list[Window]:
    merged: list[Window] = []
    for w in sorted(windows, key=lambda w: w.start):
        if merged and w.start <= merged[-1].end:
            merged[-1] = Window(merged[-1].start, max(merged[-1].end, w.end))
        else:
            merged.append(w)
    return merged


def subtract(span: Window, busy: list[Window]) -> list[Window]:
    free: list[Window] = []
    cursor = span.start
    for w in merge([b for b in busy if b.overlaps(span)]):
        if w.start > cursor:
            free.append(Window(cursor, w.start))
        cursor = max(cursor, w.end)
    if cursor < span.end:
        free.append(Window(cursor, span.end))
    return free


def day_window(day: date, tz: tzinfo) -> Window:
    start = datetime.combine(day, time(0), tzinfo=tz)
    return Window(start, start + timedelta(days=1))
