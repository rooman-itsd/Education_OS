"""Pure e-office rules: file numbers, the date a holding falls due, overdue, age buckets and how long a holder kept a
file. No database, no framework; dates are Indian business dates handed in by the application layer."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta

PRIORITIES = ("normal", "urgent", "immediate")
FILE_STATUSES = ("open", "closed")
DECISIONS = ("approved", "rejected", "returned")
NOTE_KINDS = ("noting", "decision", "system")
MOVEMENT_KINDS = ("created", "forwarded", "decided", "closed", "reopened")
ATTACHMENT_KINDS = ("correspondence", "draft", "order", "reference", "other")
RECEIPT_STATUSES = ("registered", "attached")
DISPATCH_STATUSES = ("pending", "sent")
MODES = ("email", "post", "courier", "by_hand")
AGE_BUCKETS = (("0-3d", 0, 3), ("4-7d", 4, 7), ("8-15d", 8, 15), ("16-30d", 16, 30), ("30d+", 31, None))
CATEGORY_CODE = re.compile(r"^[A-Z0-9-]{2,20}$")


class RuleError(Exception):
    """A request value breaks an e-office rule. `kind` is "invalid" (422) or "conflict" (409)."""

    def __init__(self, code: str, message: str, *, kind: str = "invalid", field: str | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.kind, self.field = code, message, kind, field


def category_code(raw: str) -> str:
    """A category code as it appears in file numbers: upper case letters, digits and hyphens, 2 to 20 long."""
    code = (raw or "").strip().upper()
    if not CATEGORY_CODE.match(code):
        raise RuleError("invalid_code", "code must be 2 to 20 letters, digits or hyphens", field="code")
    return code


def file_number(code: str, year: int, sequence: int) -> str:
    """<category code>/<year>/<sequence>, e.g. ADM/2026/0007. The sequence runs per category and calendar year."""
    return f"{code}/{year}/{sequence:04d}"


def register_number(prefix: str, year: int, sequence: int) -> str:
    """Inward and outward register numbers, e.g. IN/2026/00012 and OUT/2026/00003, running per calendar year."""
    return f"{prefix}/{year}/{sequence:05d}"


def due_date(due_on: date | None, held_from: date, priority: str, default_days: dict[str, int]) -> date:
    """The date a holding falls due: the due date set when the file was sent, or else the date it was received plus
    the default days for its priority."""
    if due_on is not None:
        return due_on
    return held_from + timedelta(days=default_days[priority])


def is_overdue(due: date, today: date) -> bool:
    """Overdue from the day after the due date: a file due today is still on time."""
    return today > due


def age_bucket(days: int) -> str:
    for name, low, high in AGE_BUCKETS:
        if days >= low and (high is None or days <= high):
            return name
    return AGE_BUCKETS[0][0]  # a negative age (clock skew) counts as new


def held_hours(since: datetime, until: datetime) -> float:
    """How long a holder kept the file, in hours with two decimals."""
    return round(max((until - since).total_seconds(), 0) / 3600, 2)


def not_in_future(day: date, today: date, field: str) -> date:
    if day > today:
        raise RuleError("invalid_date", f"{field} cannot be after today", field=field)
    return day


def not_in_past(day: date | None, today: date, field: str) -> date | None:
    if day is not None and day < today:
        raise RuleError("invalid_date", f"{field} cannot be before today", field=field)
    return day
