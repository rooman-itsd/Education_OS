"""Small validators shared by the resources: the contract's enums and formats (uuid, date, date-time) and its numbers,
held as Decimal so that sums of weightages and marks are exact."""

from __future__ import annotations

import sys
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from .errors import DomainRuleError

# Accepted inputs for a contract `type: number`: int, float and Decimal. bool (a subclass of int), str and every other
# type are rejected, so nothing is converted implicitly.
NUMBER_TYPES = (int, float, Decimal)
MAX_MAGNITUDE = Decimal(sys.float_info.max)  # a technical bound (a JSON number), not a business rule


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


def optional_text(value: object, field: str, *, max_length: int = 200) -> str | None:
    """An optional free-text label; blank counts as none."""
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


def require_number(
    value: object, field: str, *, minimum: int | Decimal | None = None, maximum: int | Decimal | None = None
) -> Decimal:
    """A finite number within the bounds (contract `type: number`, `minimum`, `maximum`), as Decimal. Floats are
    converted through their shortest repr (0.1 becomes Decimal("0.1"))."""
    if isinstance(value, bool) or not isinstance(value, NUMBER_TYPES):
        raise DomainRuleError("invalid_number", f"{field} must be a number", kind="invalid", field=field)
    number = (
        value if isinstance(value, Decimal) else Decimal(repr(value)) if isinstance(value, float) else Decimal(value)
    )
    if not number.is_finite():
        raise DomainRuleError("invalid_number", f"{field} must be a finite number", kind="invalid", field=field)
    if abs(number) > MAX_MAGNITUDE:
        raise DomainRuleError("number_out_of_range", f"{field} is too large", kind="invalid", field=field)
    if minimum is not None and number < minimum:
        raise DomainRuleError("below_minimum", f"{field} must be at least {minimum}", kind="invalid", field=field)
    if maximum is not None and number > maximum:
        raise DomainRuleError("above_maximum", f"{field} must be at most {maximum}", kind="invalid", field=field)
    return number


def require_integer(value: object, field: str, *, minimum: int | None = None) -> int:
    """An integer at or above `minimum` (contract `type: integer`, `minimum`)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainRuleError("invalid_integer", f"{field} must be an integer", kind="invalid", field=field)
    if minimum is not None and value < minimum:
        raise DomainRuleError("below_minimum", f"{field} must be at least {minimum}", kind="invalid", field=field)
    return value


def require_bool(value: object, field: str) -> bool:
    if not isinstance(value, bool):
        raise DomainRuleError("invalid_boolean", f"{field} must be true or false", kind="invalid", field=field)
    return value
