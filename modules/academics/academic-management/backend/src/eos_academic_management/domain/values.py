"""Small validators shared by the resources: numeric minimums and enums from contracts/openapi.yaml, and
code uniqueness within one organisation."""

from __future__ import annotations

import sys
from collections.abc import Iterable
from decimal import Decimal

from .errors import DomainRuleError

# Accepted inputs for a contract `type: number`: int, float and Decimal. bool (a subclass of int), str,
# Fraction and every other type are rejected, so nothing is converted implicitly.
NUMBER_TYPES = (int, float, Decimal)
# The largest magnitude a JSON number can carry between clients (a finite IEEE 754 double). Float inputs
# cannot exceed it; int and Decimal inputs are held to the same bound. It is a technical limit, not a business
# rule: the contract sets no maximum.
MAX_MAGNITUDE = Decimal(sys.float_info.max)


def require_number(value: object, field: str, *, minimum: int) -> Decimal:
    """A finite number at or above `minimum` (contract `type: number`, `minimum`), returned as Decimal so sums
    of credits are exact. Decimal inputs are kept as they are; floats are converted through their shortest
    repr (0.1 becomes Decimal("0.1")); ints exactly."""
    if isinstance(value, bool) or not isinstance(value, NUMBER_TYPES):
        raise DomainRuleError("invalid_number", f"{field} must be a number", kind="invalid", field=field)
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, float):
        number = Decimal(repr(value))
    else:
        number = Decimal(value)
    if not number.is_finite():  # NaN, sNaN, +Infinity, -Infinity; checked before any comparison
        raise DomainRuleError("invalid_number", f"{field} must be a finite number", kind="invalid", field=field)
    if abs(number) > MAX_MAGNITUDE:
        raise DomainRuleError("number_out_of_range", f"{field} is too large", kind="invalid", field=field)
    if number < minimum:
        raise DomainRuleError("below_minimum", f"{field} must be at least {minimum}", kind="invalid", field=field)
    return number


def require_integer(value: object, field: str, *, minimum: int) -> int:
    """An integer at or above `minimum` (contract `type: integer`, `minimum`)."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise DomainRuleError("invalid_integer", f"{field} must be an integer", kind="invalid", field=field)
    if value < minimum:
        raise DomainRuleError("below_minimum", f"{field} must be at least {minimum}", kind="invalid", field=field)
    return value


def require_choice(value: object, field: str, choices: tuple[str, ...]) -> str:
    """One of the values of a contract enum."""
    if value not in choices:
        raise DomainRuleError(
            "invalid_choice", f"{field} must be one of {', '.join(choices)}", kind="invalid", field=field
        )
    return str(value)


def ensure_unique_code(code: str, existing_codes: Iterable[str]) -> None:
    """Codes are unique within one organisation. FR-6 states it for courses; the contract's Conflict response
    ("duplicate code") applies it to every create that takes a code. Comparison is exact: neither the PRD nor
    the contract says whether codes are case-insensitive (open question). `code` is a required string in every
    create request of the contract, so anything else is rejected."""
    if not isinstance(code, str):
        raise DomainRuleError("invalid_code", "code must be a string", kind="invalid", field="code")
    if code in set(existing_codes):
        raise DomainRuleError("duplicate_code", f"code {code!r} is already in use", kind="conflict", field="code")
