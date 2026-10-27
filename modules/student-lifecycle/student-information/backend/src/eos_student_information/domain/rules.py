"""Domain rules and pure domain functions for student-information. No framework or database dependencies."""

from __future__ import annotations

import re
import secrets
from datetime import UTC, datetime

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
