"""Small validators shared by the resources: the contract's enums and formats (uuid, time, date, date-time)."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, time

from .errors import DomainRuleError

MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
DAYS_OF_WEEK = (MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY, SATURDAY, SUNDAY)  # contract DayOfWeek, Monday = 0


def weekday_name(day: date) -> str:
    return DAYS_OF_WEEK[day.weekday()]


def require_choice(value: object, field: str, choices: tuple[str, ...]) -> str:
    """One of the values of a contract enum."""
    if value not in choices:
        raise DomainRuleError(
            "invalid_choice", f"{field} must be one of {', '.join(choices)}", kind="invalid", field=field
        )
    return str(value)


def require_id(value: object, field: str) -> str:
    """An id of this module or an external module (contract `format: uuid`), kept as the plain string."""
    if not isinstance(value, str):
        raise DomainRuleError("invalid_id", f"{field} must be a uuid", kind="invalid", field=field)
    try:
        uuid.UUID(value)
    except ValueError:
        raise DomainRuleError("invalid_id", f"{field} must be a uuid", kind="invalid", field=field) from None
    return value


def require_time(value: object, field: str) -> time:
    """A wall-clock time (contract `format: time`). datetime is not a time, and an offset has no meaning for a slot
    that repeats weekly in the organisation's time zone, so a time with tzinfo is rejected."""
    if not isinstance(value, time) or value.tzinfo is not None:
        raise DomainRuleError("invalid_time", f"{field} must be a time without a zone", kind="invalid", field=field)
    return value


def require_date(value: object, field: str) -> date:
    """A calendar date (contract `format: date`). datetime is a subclass of date but carries a time."""
    if isinstance(value, datetime) or not isinstance(value, date):
        raise DomainRuleError("invalid_date", f"{field} must be a date without a time", kind="invalid", field=field)
    return value


def require_instant(value: object, field: str) -> datetime:
    """A moment (contract `format: date-time`) with a zone, returned in UTC."""
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise DomainRuleError(
            "invalid_datetime", f"{field} must be a date and time with a zone", kind="invalid", field=field
        )
    return value.astimezone(UTC)


def require_text(value: object, field: str, *, max_length: int | None = None) -> str:
    """A non-blank string, stripped."""
    if not isinstance(value, str) or not value.strip():
        raise DomainRuleError("invalid_text", f"{field} must not be blank", kind="invalid", field=field)
    text = value.strip()
    if max_length is not None and len(text) > max_length:
        raise DomainRuleError(
            "text_too_long", f"{field} must be at most {max_length} characters", kind="invalid", field=field
        )
    return text


def optional_label(value: object, field: str, *, max_length: int = 200) -> str | None:
    """An optional free-text label (location); blank counts as none."""
    if value is None:
        return None
    if not isinstance(value, str):
        raise DomainRuleError("invalid_text", f"{field} must be a string", kind="invalid", field=field)
    text = value.strip()
    if not text:
        return None
    if len(text) > max_length:
        raise DomainRuleError(
            "text_too_long", f"{field} must be at most {max_length} characters", kind="invalid", field=field
        )
    return text
