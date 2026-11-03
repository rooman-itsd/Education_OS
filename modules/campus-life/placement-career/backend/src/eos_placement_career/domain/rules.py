"""Pure placement-career rules: the statuses and the fixed application sequence, field values (names, URLs, emails,
money, positions, eligibility criteria and declarations) and the date rules of drives and openings. No database, no
framework; dates are Indian business dates handed in by the application layer."""

from __future__ import annotations

import re
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from urllib.parse import urlsplit

DRIVE_STATUSES = ("draft", "scheduled", "completed", "cancelled")
OPENING_STATUSES = ("draft", "open", "closed", "cancelled")
APPLICATION_STATUSES = (
    "applied",
    "shortlisted",
    "in_process",
    "offered",
    "accepted",
    "declined",
    "rejected",
    "withdrawn",
)
# The statuses an officer may move an application to (StatusChange.status in the contract).
STEPS = ("shortlisted", "in_process", "offered", "accepted", "declined", "rejected")

# The fixed sequence: one step at a time, never back. rejected (officer) and withdrawn (student) end an application
# from the first three statuses; accepted, declined, rejected and withdrawn are final.
NEXT = {
    "applied": ("shortlisted",),
    "shortlisted": ("in_process",),
    "in_process": ("offered",),
    "offered": ("accepted", "declined"),
}
ENDABLE = ("applied", "shortlisted", "in_process")
FINAL = ("accepted", "declined", "rejected", "withdrawn")

# Drives and openings a caller without the matching manage permission may see.
PUBLIC_DRIVE_STATUSES = ("scheduled", "completed")
PUBLIC_OPENING_STATUSES = ("open", "closed")

CENT = Decimal("0.01")
MAX_AMOUNT = Decimal("1000000000000")  # Numeric(14, 2) holds 12 digits before the point
MONEY = re.compile(r"^[0-9]+(\.[0-9]{1,2})?$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
NAME_MAX = 200
TITLE_MAX = 200
MAX_CGPA = 10


class RuleError(Exception):
    """A request value breaks a placement-career rule. `kind` is "invalid" (422) or "conflict" (409)."""

    def __init__(self, code: str, message: str, *, kind: str = "invalid", field: str | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.kind, self.field = code, message, kind, field


def clean(value: str | None) -> str | None:
    """Trimmed text, or None for a missing or blank value."""
    out = (value or "").strip()
    return out or None


def company_name(raw: str | None) -> str:
    name = clean(raw)
    if name is None or len(name) > NAME_MAX:
        raise RuleError("invalid_name", f"name must be 1 to {NAME_MAX} characters", field="name")
    return name


def name_key(name: str) -> str:
    """Two company names are the same when they differ only in case and spacing."""
    return " ".join(name.split()).casefold()


def title(raw: str | None) -> str:
    out = clean(raw)
    if out is None or len(out) > TITLE_MAX:
        raise RuleError("invalid_title", f"title must be 1 to {TITLE_MAX} characters", field="title")
    return out


def website(raw: str | None) -> str | None:
    url = clean(raw)
    if url is None:
        return None
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.netloc or any(c.isspace() for c in url):
        raise RuleError("invalid_url", "website must be an http(s) URL", field="website")
    return url


def email(raw: str | None) -> str | None:
    out = clean(raw)
    if out is None:
        return None
    if not EMAIL.match(out):
        raise RuleError("invalid_email", "contact_email must be an email address", field="contact_email")
    return out


def money(raw, field: str = "ctc_per_annum") -> Decimal | None:
    """A Money value of the contract: a decimal string in rupees, not negative, at most two decimals."""
    if raw is None:
        return None
    if not isinstance(raw, str) or not MONEY.match(raw.strip()):
        raise RuleError("invalid_amount", f"{field} must be a decimal string in rupees, not negative", field=field)
    try:
        value = Decimal(raw.strip())
    except InvalidOperation as e:  # pragma: no cover - the pattern already refuses anything Decimal cannot read
        raise RuleError("invalid_amount", f"{field} is not an amount", field=field) from e
    if value >= MAX_AMOUNT:
        raise RuleError("invalid_amount", f"{field} is too large", field=field)
    return value.quantize(CENT, ROUND_HALF_UP)


def money_text(value: Decimal | None) -> str | None:
    return None if value is None else f"{Decimal(value).quantize(CENT, ROUND_HALF_UP):.2f}"


def positions(value: int | None) -> int | None:
    if value is not None and value < 1:
        raise RuleError("invalid_positions", "positions must be at least 1", field="positions")
    return value


def _cgpa(value, field: str) -> float | None:
    if value is None:
        return None
    if not 0 <= value <= MAX_CGPA:
        raise RuleError("invalid_eligibility", f"{field} must be between 0 and {MAX_CGPA}", field=field)
    return float(value)


def _backlogs(value, field: str) -> int | None:
    if value is not None and value < 0:
        raise RuleError("invalid_eligibility", f"{field} cannot be negative", field=field)
    return value


def eligibility(raw: dict | None) -> dict:
    """Criteria shown to students, never enforced. Every field is optional; an empty list or null is no criterion."""
    raw = raw or {}
    programmes = []
    for p in raw.get("programmes") or []:
        name = clean(p)
        if name is None:
            raise RuleError("invalid_eligibility", "a programme cannot be empty", field="eligibility.programmes")
        programmes.append(name)
    return {
        "programmes": programmes,
        "graduating_years": list(raw.get("graduating_years") or []),
        "min_cgpa": _cgpa(raw.get("min_cgpa"), "eligibility.min_cgpa"),
        "max_active_backlogs": _backlogs(raw.get("max_active_backlogs"), "eligibility.max_active_backlogs"),
        "notes": clean(raw.get("notes")),
    }


def declaration(raw: dict | None) -> dict:
    """What a student states about themselves when applying. Ranges are checked, the content is not."""
    raw = raw or {}
    return {
        "programme": clean(raw.get("programme")),
        "graduating_year": raw.get("graduating_year"),
        "cgpa": _cgpa(raw.get("cgpa"), "declared.cgpa"),
        "active_backlogs": _backlogs(raw.get("active_backlogs"), "declared.active_backlogs"),
    }


def not_before(day: date | None, today: date, field: str) -> date | None:
    if day is not None and day < today:
        raise RuleError("invalid_date", f"{field} cannot be before today", field=field)
    return day


def drive_dates(scheduled_on: date, ends_on: date | None, registration_closes_on: date | None) -> None:
    """A drive ends on or after its date and registration closes on or before it."""
    if ends_on is not None and ends_on < scheduled_on:
        raise RuleError("invalid_date", "ends_on cannot be before scheduled_on", field="ends_on")
    if registration_closes_on is not None and registration_closes_on > scheduled_on:
        raise RuleError(
            "invalid_date", "registration_closes_on cannot be after scheduled_on", field="registration_closes_on"
        )


def within_drive(applications_close_on: date, drive_on: date) -> None:
    """An opening in a drive stops taking applications on or before the drive date."""
    if applications_close_on > drive_on:
        raise RuleError(
            "close_date_after_drive",
            "applications_close_on cannot be after the drive date",
            field="applications_close_on",
        )


def step(current: str, target: str) -> str:
    """The officer's move of an application: `target` must be the next step from `current`, or rejected from an
    application that has not reached an offer."""
    if target not in STEPS:
        raise RuleError("invalid_status", "status must be one of " + ", ".join(STEPS), field="status")
    if target == "rejected":
        allowed = current in ENDABLE
    else:
        allowed = target in NEXT.get(current, ())
    if not allowed:
        raise RuleError("invalid_transition", f"an application {current} cannot move to {target}", kind="conflict")
    return target


def withdrawable(status: str) -> bool:
    """The student withdraws before an offer, from the same statuses the officer can reject from."""
    return status in ENDABLE
