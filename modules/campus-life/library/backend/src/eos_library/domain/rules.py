"""Domain rules of library (docs/prd.md, "Main flows" and "Rules"). Pure functions and constants: no framework,
no database. The application layer calls these before it changes state. Money is exact: Decimal, two places."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

# ---------------------------------------------------------------- statuses (contracts/openapi.yaml)

COPY_STATUSES = ("available", "on-loan", "on-hold", "lost", "withdrawn")
LOAN_STATUSES = ("active", "returned", "lost")
RESERVATION_STATUSES = ("waiting", "ready", "fulfilled", "cancelled", "expired")
FINE_STATUSES = ("open", "paid", "waived")
FINE_REASONS = ("overdue", "lost", "damage")
ACCESS_TYPES = ("open", "campus", "licensed")

# A reservation in one of these still holds a place (one per title per person).
RESERVATION_ACTIVE = ("waiting", "ready")

# Refusal codes from the contract's Refusal schema.
NOT_A_MEMBER = "not-a-member"
MEMBER_BLOCKED = "member-blocked"
LOAN_LIMIT = "loan-limit"
UNPAID_FINES = "unpaid-fines"
COPY_UNAVAILABLE = "copy-unavailable"
HELD_FOR_OTHER = "held-for-other"
NO_RENEWALS_LEFT = "no-renewals-left"
TITLE_RESERVED = "title-reserved"

DEFAULT_HOLD_DAYS = 3
CENT = Decimal("0.01")
MONEY_RE = re.compile(r"^[0-9]+(\.[0-9]{1,2})?$")


class RuleViolationError(Exception):
    """A domain rule refused the change. `code` is stable; the API maps it to a status."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class RefusedError(RuleViolationError):
    """A circulation refusal with one of the contract's Refusal codes (answered with 409)."""


# ---------------------------------------------------------------- money


def money(value: Decimal | int | str | None) -> Decimal:
    """An exact amount with two decimal places."""
    if value is None:
        return Decimal("0.00")
    return Decimal(value).quantize(CENT, rounding=ROUND_HALF_UP)


def parse_money(text: str) -> Decimal:
    """A Money string from the API (`^[0-9]+(\\.[0-9]{1,2})?$`)."""
    if not isinstance(text, str) or not MONEY_RE.match(text):
        raise RuleViolationError("invalid_amount", f"{text!r} is not an amount like 25.00")
    try:
        return money(text)
    except InvalidOperation as e:
        raise RuleViolationError("invalid_amount", f"{text!r} is not an amount") from e


def money_str(value: Decimal | None) -> str:
    return f"{money(value):.2f}"


# ---------------------------------------------------------------- policies and fines


@dataclass(frozen=True)
class Policy:
    """The loan policy for one member category."""

    max_loans: int
    loan_days: int
    max_renewals: int
    fine_per_day: Decimal
    max_unpaid_fines: Decimal
    hold_days: int = DEFAULT_HOLD_DAYS


def days_late(due_on: date, on: date) -> int:
    """Whole days past the due date; returning on the due date is on time."""
    return max(0, (on - due_on).days)


def overdue_fine(due_on: date, on: date, fine_per_day: Decimal) -> Decimal:
    return money(Decimal(days_late(due_on, on)) * money(fine_per_day))


def due_date(issued_on: date, loan_days: int) -> date:
    return issued_on + timedelta(days=loan_days)


# ---------------------------------------------------------------- issue and renew


def check_issue(
    *,
    is_member: bool,
    blocked: bool,
    policy: Policy | None,
    active_loans: int,
    unpaid_fines: Decimal,
    copy_status: str,
    held_for: str | None,
    person_id: str,
) -> None:
    """Why a copy may not be issued to this person, in the order a librarian would explain it."""
    if not is_member:
        raise RefusedError(NOT_A_MEMBER, "the person is not a library member")
    if blocked:
        raise RefusedError(MEMBER_BLOCKED, "the member is blocked from borrowing")
    if policy is None:
        raise RefusedError(LOAN_LIMIT, "there is no loan policy for the member's category")
    if active_loans >= policy.max_loans:
        raise RefusedError(LOAN_LIMIT, f"the member already has {active_loans} of {policy.max_loans} loans")
    if money(unpaid_fines) > money(policy.max_unpaid_fines):
        raise RefusedError(UNPAID_FINES, f"unpaid fines {money_str(unpaid_fines)} are over the limit")
    if copy_status == "on-hold":
        if held_for != person_id:
            raise RefusedError(HELD_FOR_OTHER, "the copy is held for another member's reservation")
        return
    if copy_status != "available":
        raise RefusedError(COPY_UNAVAILABLE, f"the copy is {copy_status}")


def check_renew(*, renewals: int, policy: Policy, someone_waiting: bool) -> None:
    if renewals >= policy.max_renewals:
        raise RefusedError(NO_RENEWALS_LEFT, "no renewals are left on this loan")
    if someone_waiting:
        raise RefusedError(TITLE_RESERVED, "another member is waiting for this title")


def renewals_left(renewals: int, policy: Policy | None) -> int:
    return max(0, (policy.max_renewals if policy else 0) - renewals)


# ---------------------------------------------------------------- reservations


def hold_expiry(on: date, hold_days: int) -> date:
    """The last day a held copy waits to be collected."""
    return on + timedelta(days=max(1, hold_days))


def hold_expired(hold_expires_on: date | None, today: date) -> bool:
    return hold_expires_on is not None and hold_expires_on < today
