"""Business-hours calendars and business time (PRD "Rules": business time counts only inside the calendar's working
intervals, in its time zone, skipping its holidays; an always_open calendar counts every minute).

Working intervals are local wall-clock times per ISO weekday. Each one is turned into a UTC window for each local
date, so daylight-saving changes are followed: a window that loses an hour to a clock change counts the real minutes
that remain. Holidays are local dates.

Bounds, so date arithmetic can never overflow:
- the module accepts instants from EARLIEST to LATEST only (helpdesk times outside them are malformed);
- a due time is searched at most HORIZON_DAYS ahead (or back); a target the calendar cannot reach inside that is
  "unreachable", which a policy or calendar change refuses with 422.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .errors import DomainRuleError

MINUTES_PER_DAY = 24 * 60
# A target is at most a year of round-the-clock minutes; also the bound of every minutes field of a policy.
MAX_TARGET_MINUTES = 366 * MINUTES_PER_DAY
# How far a due time is searched: ten years.
HORIZON_DAYS = 3653
# Instants the module works with. Helpdesk times outside these are refused as malformed; with HORIZON_DAYS added
# they stay far from datetime.min and datetime.max.
EARLIEST = datetime(2000, 1, 1, tzinfo=UTC)
LATEST = datetime(2100, 1, 1, tzinfo=UTC)
# Holiday dates the module accepts; anything else is a typing mistake, never a real holiday.
FIRST_HOLIDAY, LAST_HOLIDAY = date(2000, 1, 1), date(2099, 12, 31)
MAX_ZONE_NAME = 64

UTC_NAMES = ("UTC", "Etc/UTC")


def _invalid(code: str, message: str, field: str) -> DomainRuleError:
    return DomainRuleError(code, message, kind="invalid", field=field)


def zone(name: str) -> tzinfo:
    """The IANA time zone `name`, from the host's time-zone database (UTC always works). 422 when unknown."""
    if not isinstance(name, str) or not 0 < len(name) <= MAX_ZONE_NAME:
        raise _invalid("unknown_time_zone", "time_zone must be an IANA time zone such as Asia/Kolkata", "time_zone")
    if name in UTC_NAMES:
        return UTC
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError, OSError, TypeError):
        raise _invalid("unknown_time_zone", f"unknown time zone {name!r}", "time_zone") from None


def minute_of_day(value: str, *, end: bool) -> int:
    """HH:MM as minutes after midnight. Only an end may be 24:00 (end of day)."""
    try:
        hours, minutes = (int(part) for part in value.split(":"))
    except (AttributeError, ValueError):
        raise _invalid("invalid_time", f"{value!r} is not a time HH:MM", "working_hours") from None
    total = hours * 60 + minutes
    if not 0 <= minutes < 60 or not 0 <= total <= (MINUTES_PER_DAY if end else MINUTES_PER_DAY - 1):
        raise _invalid("invalid_time", f"{value!r} is not a time of day{' or 24:00' if end else ''}", "working_hours")
    return total


@dataclass(frozen=True)
class BusinessCalendar:
    tz: tzinfo
    always_open: bool
    # ISO weekday -> sorted, non-overlapping (start minute, end minute) local intervals
    hours: dict[int, tuple[tuple[int, int], ...]]
    holidays: frozenset[date]


def check_calendar(time_zone: str, always_open: bool, working_hours: list[dict], holidays: list[dict]) -> None:
    """422 for an unknown time zone, an interval whose end is not after its start, overlapping intervals on one
    weekday, holidays outside 2000 to 2099, or no working hours on a calendar that is not always open."""
    zone(time_zone)
    for holiday in holidays:
        if not FIRST_HOLIDAY <= holiday["date"] <= LAST_HOLIDAY:
            raise _invalid("invalid_holiday", "holiday dates must be between 2000-01-01 and 2099-12-31", "holidays")
    if always_open:
        _intervals(working_hours)  # still checked, though ignored while always_open
        return
    if not working_hours:
        raise _invalid("working_hours_required", "working_hours are required unless always_open", "working_hours")
    _intervals(working_hours)


def _intervals(working_hours: list[dict]) -> dict[int, tuple[tuple[int, int], ...]]:
    by_day: dict[int, list[tuple[int, int]]] = {}
    for interval in working_hours:
        start = minute_of_day(interval["start"], end=False)
        end = minute_of_day(interval["end"], end=True)
        if end <= start:
            raise _invalid("end_before_start", "each working interval must end after it starts", "working_hours")
        by_day.setdefault(int(interval["weekday"]), []).append((start, end))
    result = {}
    for weekday, spans in by_day.items():
        spans.sort()
        for (_, prev_end), (next_start, _) in zip(spans, spans[1:], strict=False):
            if next_start < prev_end:
                raise _invalid("overlapping_hours", "working intervals of one weekday overlap", "working_hours")
        result[weekday] = tuple(spans)
    return result


def build(time_zone: str, always_open: bool, working_hours: list[dict], holidays: list[dict]) -> BusinessCalendar:
    """A calendar from its stored (already checked) values."""
    return BusinessCalendar(
        tz=zone(time_zone),
        always_open=bool(always_open),
        hours={} if always_open else _intervals(working_hours or []),
        holidays=frozenset(
            date.fromisoformat(h["date"]) if isinstance(h["date"], str) else h["date"] for h in holidays
        ),
    )


def in_range(at: datetime) -> bool:
    return EARLIEST <= at < LATEST


def _instant(cal: BusinessCalendar, day: date, minute: int) -> datetime:
    local = datetime(day.year, day.month, day.day) + timedelta(minutes=minute)
    return local.replace(tzinfo=cal.tz).astimezone(UTC)


def _windows(cal: BusinessCalendar, day: date) -> list[tuple[datetime, datetime]]:
    """The UTC windows of one local date, in order, merged where a clock change makes them touch."""
    if day in cal.holidays:
        return []
    windows: list[tuple[datetime, datetime]] = []
    for start, end in cal.hours.get(day.isoweekday(), ()):
        a, b = _instant(cal, day, start), _instant(cal, day, end)
        if b <= a:
            continue
        if windows and a <= windows[-1][1]:
            windows[-1] = (windows[-1][0], max(windows[-1][1], b))
        else:
            windows.append((a, b))
    return windows


def shift(cal: BusinessCalendar, start: datetime, minutes: int) -> datetime | None:
    """The instant `minutes` business minutes after `start` (before it when negative). None when that lies more than
    HORIZON_DAYS away (the calendar has too few working hours for it)."""
    start = start.astimezone(UTC)
    if minutes == 0:
        return start
    if cal.always_open:
        if abs(minutes) > HORIZON_DAYS * MINUTES_PER_DAY:
            return None
        return start + timedelta(minutes=minutes)
    remaining = timedelta(minutes=abs(minutes))
    first = start.astimezone(cal.tz).date()
    if minutes > 0:
        for offset in range(HORIZON_DAYS + 1):
            for a, b in _windows(cal, first + timedelta(days=offset)):
                if b <= start:
                    continue
                a = max(a, start)
                if remaining <= b - a:
                    return a + remaining
                remaining -= b - a
        return None
    for offset in range(HORIZON_DAYS + 1):
        for a, b in reversed(_windows(cal, first - timedelta(days=offset))):
            if a >= start:
                continue
            b = min(b, start)
            if remaining <= b - a:
                return b - remaining
            remaining -= b - a
    return None


def between(cal: BusinessCalendar, start: datetime, end: datetime) -> int:
    """Whole business minutes from `start` to `end`; 0 when end is not after start."""
    start, end = start.astimezone(UTC), end.astimezone(UTC)
    if end <= start:
        return 0
    if cal.always_open:
        return int((end - start).total_seconds() // 60)
    total = timedelta(0)
    day, last = start.astimezone(cal.tz).date(), end.astimezone(cal.tz).date()
    while day <= last:
        for a, b in _windows(cal, day):
            a, b = max(a, start), min(b, end)
            if b > a:
                total += b - a
        day += timedelta(days=1)
    return int(total.total_seconds() // 60)


def reachable(cal: BusinessCalendar, start: datetime, minutes: int) -> bool:
    return shift(cal, start, minutes) is not None
