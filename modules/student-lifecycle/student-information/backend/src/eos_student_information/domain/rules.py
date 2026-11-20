"""Domain rules and pure domain functions for student-information. No framework or database dependencies."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, date, datetime

from .enums import PERSON_STATUSES


class RuleViolationError(Exception):
    """Domain rule violation. `code` matches contract error codes (RuleError / ConflictError)."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def validate_status_change(current_status: str, new_status: str, reason: str | None) -> None:
    """Validates person status transition according to contract rules."""
    if new_status not in PERSON_STATUSES:
        raise RuleViolationError("invalid_status", f"Unknown status: {new_status}")
    if new_status == current_status:
        raise RuleViolationError("status_unchanged", f"Status unchanged: person is already {current_status}")
    if not reason or not reason.strip():
        raise RuleViolationError("reason_required", "A reason is required for any status change")


AGE_OF_MAJORITY = 18


def adult_cutoff(today: date) -> date:
    """The latest date of birth of a person who is 18 or older on `today` (their 18th birthday is today or earlier).

    For a 29 February `today`, 18 years earlier is not a leap year, so the cutoff is 28 February: someone born on
    1 March of that year is still 17."""
    year = today.year - AGE_OF_MAJORITY
    try:
        return today.replace(year=year)
    except ValueError:
        return today.replace(year=year, day=28)


def is_minor(date_of_birth: date | None, today: date) -> bool | None:
    """True when the person is under 18 on `today`, False when 18 or older, None when the date of birth is unknown.

    DPDP Act s.2(f): a child is a person under eighteen. The platform records the guardian's consent; it never blocks
    anything on this value (gap D7)."""
    if date_of_birth is None:
        return None
    return date_of_birth > adult_cutoff(today)


def validate_consent_date(obtained_on: date, today: date) -> None:
    """The guardian's consent is recorded after it was obtained offline, so its date cannot be in the future."""
    if obtained_on > today:
        raise RuleViolationError(
            "consent_date_in_future", f"obtained_on {obtained_on.isoformat()} is after today ({today.isoformat()})"
        )


def generate_card_number(organisation_id: str, when: datetime | None = None) -> str:
    """Generates an identity card number according to pattern IDC-{ORG4}-{YYYYMM}-{RANDOM6}.

    Uses secrets.token_hex(3).upper() as a cryptographically strong random source.
    """
    clean_org = re.sub(r"[^A-Za-z0-9]", "", organisation_id)
    org_part = clean_org[:4].upper().ljust(4, "X")
    timestamp = when or datetime.now(UTC)
    date_part = timestamp.strftime("%Y%m")
    random_part = secrets.token_hex(3).upper()
    return f"IDC-{org_part}-{date_part}-{random_part}"
