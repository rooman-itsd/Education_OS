"""Dates of an Indian public authority. A request is received, answered and appealed on a calendar day in India, so
"today" is the date in IST (UTC+05:30, no daylight saving), not in UTC: a request recorded at 02:00 IST on the 6th is
recorded on the 6th, although UTC still says the 5th. Pure Python.

Counting days (RTI_DAY_COUNTING):
- calendar: every day counts.
- working: Monday to Friday count; Saturday and Sunday do not. There is no holiday calendar in the repository, so
  public holidays count as working days (README "Assumptions to revisit").
In both, the day of the event itself is day 0: a request received on the 1st with 30 calendar days is due on the 31st.
A due date is met until the end of that day in IST.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30), "IST")

CALENDAR, WORKING = "calendar", "working"
DAY_COUNTINGS = (CALENDAR, WORKING)

# Dates the module accepts anywhere (request bodies and query parameters). The contract sets no range; a date outside
# these years is a typing mistake, and the bound keeps every date sum far from date.min and date.max.
MIN_DATE, MAX_DATE = date(1900, 1, 1), date(2199, 12, 31)


def today_in_india(now: datetime) -> date:
    """The calendar date in India at the instant `now`."""
    return now.astimezone(IST).date()


def add_days(start: date, days: int, counting: str = CALENDAR) -> date:
    """`start` plus `days` days, counted as calendar or working days. `days` is a settings value (1 to 365)."""
    if days < 0:
        raise ValueError("days must not be negative")
    if counting == CALENDAR:
        return start + timedelta(days=days)
    if counting != WORKING:
        raise ValueError(f"unknown day counting {counting!r}")
    day = start
    left = days
    while left:
        day += timedelta(days=1)
        if day.weekday() < 5:  # Monday is 0, Saturday is 5
            left -= 1
    return day


def end_of_day(day: date) -> datetime:
    """The last second of `day` in IST, as a UTC instant: when a due date stops being met."""
    return datetime.combine(day, time(23, 59, 59), tzinfo=IST).astimezone(UTC)
