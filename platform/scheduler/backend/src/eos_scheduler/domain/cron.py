"""Five-field cron (minute hour day-of-month month day-of-week) evaluated in an explicit timezone.

Supported per field: `*`, a number, `a-b`, lists `a,b`, and steps `*/n` or `a-b/n`. Day of week is 0-6 from
Sunday, with 7 also Sunday. As in classic cron, when both day fields are restricted a day matches if EITHER
does. No names (`MON`, `JAN`) and no `@daily`: a timing a reviewer has to look up is a timing nobody checks.

Times are found in the schedule's own timezone and returned in UTC. A wall-clock time that does not exist on a
daylight-saving change (02:30 on the spring-forward night) fires at the first minute after it that does; one
that happens twice fires once."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

FIELDS = (("minute", 0, 59), ("hour", 0, 23), ("day", 1, 31), ("month", 1, 12), ("weekday", 0, 7))
HORIZON = timedelta(days=366 * 5)  # no valid expression is further apart than this (29 Feb on a Monday...)


class CronError(ValueError):
    pass


def _field(text: str, name: str, low: int, high: int) -> frozenset[int]:
    values: set[int] = set()
    for part in text.split(","):
        body, _, step_text = part.partition("/")
        step = 1
        if step_text:
            if not step_text.isdigit() or int(step_text) == 0:
                raise CronError(f"{name}: bad step in {part!r}")
            step = int(step_text)
        if body == "*":
            start, end = low, high
        elif "-" in body:
            a, _, b = body.partition("-")
            if not (a.isdigit() and b.isdigit()):
                raise CronError(f"{name}: bad range {part!r}")
            start, end = int(a), int(b)
        elif body.isdigit():
            start = end = int(body)
            if step_text:
                end = high
        else:
            raise CronError(f"{name}: {part!r} is not a number, range or *")
        if not low <= start <= end <= high:
            raise CronError(f"{name}: {part!r} is outside {low}-{high}")
        values.update(range(start, end + 1, step))
    return frozenset(values)


@dataclass(frozen=True)
class Cron:
    expression: str
    minutes: frozenset[int]
    hours: frozenset[int]
    days: frozenset[int]
    months: frozenset[int]
    weekdays: frozenset[int]  # 0 = Sunday
    any_day: bool
    any_weekday: bool

    @classmethod
    def parse(cls, expression: str) -> Cron:
        parts = expression.split()
        if len(parts) != 5:
            raise CronError("a cron has five fields: minute hour day-of-month month day-of-week")
        m, h, d, mo, w = (_field(p, *spec) for p, spec in zip(parts, FIELDS, strict=True))
        return cls(
            expression=" ".join(parts),
            minutes=m,
            hours=h,
            days=d,
            months=mo,
            weekdays=frozenset(x % 7 for x in w),
            any_day=parts[2] == "*",
            any_weekday=parts[4] == "*",
        )

    def _day_matches(self, local: datetime) -> bool:
        day_ok = local.day in self.days
        weekday_ok = (local.isoweekday() % 7) in self.weekdays
        if self.any_day and self.any_weekday:
            return True
        if self.any_day:
            return weekday_ok
        if self.any_weekday:
            return day_ok
        return day_ok or weekday_ok

    def next_after(self, after: datetime, timezone: str) -> datetime:
        """The first firing strictly after `after` (aware), as an aware UTC datetime."""
        tz = zone(timezone)
        local = after.astimezone(tz).replace(second=0, microsecond=0, tzinfo=None) + timedelta(minutes=1)
        limit = local + HORIZON
        while local < limit:
            if local.month not in self.months:
                local = (local.replace(day=1, hour=0, minute=0) + timedelta(days=32)).replace(day=1)
                continue
            if not self._day_matches(local):
                local = local.replace(hour=0, minute=0) + timedelta(days=1)
                continue
            if local.hour not in self.hours:
                local = local.replace(minute=0) + timedelta(hours=1)
                continue
            if local.minute not in self.minutes:
                local += timedelta(minutes=1)
                continue
            fired = _to_utc(local, tz)
            if fired > after:
                return fired
            local += timedelta(minutes=1)  # the repeated hour of a fall-back night: already fired
        raise CronError(f"{self.expression!r} never fires")


def _to_utc(local: datetime, tz: ZoneInfo) -> datetime:
    aware = local.replace(tzinfo=tz)
    # A wall time skipped by a spring-forward change round-trips to a different one: move to the first real one.
    if aware.astimezone(UTC).astimezone(tz).replace(tzinfo=None) != local:
        aware = (aware.astimezone(UTC)).astimezone(tz)
    return aware.astimezone(UTC)


def zone(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError) as e:
        raise CronError(f"unknown timezone {name!r}") from e
