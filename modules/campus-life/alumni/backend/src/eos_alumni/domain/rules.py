"""Pure alumni rules: the values of a directory record, the dates of an assignment and the values of a session. No
database, no framework; "today" and "now" are handed in by the application layer (today is the Asia/Kolkata date)."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime
from urllib.parse import urlsplit

ALUMNUS_STATUSES = ("active", "archived")
ASSIGNMENT_STATUSES = ("active", "ended")
SESSION_STATUSES = ("scheduled", "completed", "cancelled")
SESSION_MODES = ("in_person", "online", "phone")

NAME_MAX = 200  # full_name and the other short fields (contract maxLength)
CONTACT_MAX = 200  # email, phone, linkedin_url
FIRST_GRADUATION_YEAR = 1900
MIN_DURATION, MAX_DURATION = 1, 480
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
PHONE = re.compile(r"^\+?[0-9 ().-]+$")
PHONE_DIGITS = (7, 15)  # an Indian mobile has 10, an international number at most 15 (E.164)


class RuleError(Exception):
    """A request value breaks an alumni rule. `kind` is "invalid" (422) or "conflict" (409)."""

    def __init__(self, code: str, message: str, *, kind: str = "invalid", field: str | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.kind, self.field = code, message, kind, field


def optional_text(value: str | None) -> str | None:
    """Free text with surrounding spaces removed; blank means not given."""
    out = (value or "").strip()
    return out or None


def full_name(value: str | None) -> str:
    name = (value or "").strip()
    if not name or len(name) > NAME_MAX:
        raise RuleError("invalid_name", f"full_name must be 1 to {NAME_MAX} characters", field="full_name")
    return name


def graduation_year(value: int, this_year: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not FIRST_GRADUATION_YEAR <= value <= this_year:
        raise RuleError(
            "invalid_graduation_year",
            f"graduation_year must be between {FIRST_GRADUATION_YEAR} and {this_year}",
            field="graduation_year",
        )
    return value


def email(value: str | None) -> str | None:
    out = optional_text(value)
    if out is not None and (len(out) > CONTACT_MAX or not EMAIL.match(out)):
        raise RuleError("invalid_email", "email is not a valid address", field="email")
    return out


def phone(value: str | None) -> str | None:
    """Digits with an optional leading +, spaces, dots, hyphens and brackets; 7 to 15 digits in all."""
    out = optional_text(value)
    if out is None:
        return None
    digits = sum(ch.isdigit() for ch in out)
    if len(out) > CONTACT_MAX or not PHONE.match(out) or not PHONE_DIGITS[0] <= digits <= PHONE_DIGITS[1]:
        raise RuleError("invalid_phone", "phone must be a telephone number of 7 to 15 digits", field="phone")
    return out


def url(value: str | None, field: str = "linkedin_url") -> str | None:
    """An absolute http or https address with a host."""
    out = optional_text(value)
    if out is None:
        return None
    try:
        parts = urlsplit(out)
    except ValueError:
        parts = None
    if len(out) > CONTACT_MAX or parts is None or parts.scheme not in ("http", "https") or not parts.netloc:
        raise RuleError("invalid_url", f"{field} must be an http or https address", field=field)
    if any(ch.isspace() for ch in out):
        raise RuleError("invalid_url", f"{field} must be an http or https address", field=field)
    return out


def started_on(day: date | None, today: date) -> date:
    """The start of an assignment: today unless given, and never after today (owner decision A7)."""
    day = day or today
    if day > today:
        raise RuleError("invalid_date", "started_on cannot be after today", field="started_on")
    return day


def ended_on(day: date | None, started: date, today: date) -> date:
    """The end of an assignment: today unless given, on or after its start and never after today (A7)."""
    day = day or today
    if day > today:
        raise RuleError("invalid_date", "ended_on cannot be after today", field="ended_on")
    if day < started:
        raise RuleError("invalid_date", "ended_on cannot be before started_on", field="ended_on")
    return day


def as_utc(moment: datetime) -> datetime:
    """A timestamp in UTC; one sent without an offset is taken as UTC (the contract's timestamps are UTC)."""
    return moment.replace(tzinfo=UTC) if moment.tzinfo is None else moment.astimezone(UTC)


def scheduled_at(moment: datetime, started: date, business_date) -> datetime:
    """A session is not before its assignment started: its Asia/Kolkata date is on or after started_on."""
    moment = as_utc(moment)
    if business_date(moment) < started:
        raise RuleError(
            "invalid_scheduled_at", "scheduled_at cannot be before the assignment started", field="scheduled_at"
        )
    return moment


def duration(minutes: int | None) -> int | None:
    if minutes is None:
        return None
    if isinstance(minutes, bool) or not MIN_DURATION <= minutes <= MAX_DURATION:
        raise RuleError(
            "invalid_duration",
            f"duration_minutes must be between {MIN_DURATION} and {MAX_DURATION}",
            field="duration_minutes",
        )
    return minutes
