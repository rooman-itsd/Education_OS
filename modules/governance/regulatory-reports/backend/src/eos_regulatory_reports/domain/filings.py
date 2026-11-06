"""Obligations and filings (PRD "Main flows" and "Statuses"): the statuses of a filing and the moves between them,
what may change in each status, and when a filing is overdue or due soon. Pure Python.

Statuses:
    open -> in_preparation -> under_review -> submitted -> acknowledged
    under_review -> in_preparation                    (returned with a comment)
    open | in_preparation -> not_applicable           (with a reason, final)
"""

from __future__ import annotations

from datetime import date

from .errors import DomainRuleError

OPEN, IN_PREPARATION, UNDER_REVIEW = "open", "in_preparation", "under_review"
SUBMITTED, ACKNOWLEDGED, NOT_APPLICABLE = "submitted", "acknowledged", "not_applicable"
FILING_STATUSES = (OPEN, IN_PREPARATION, UNDER_REVIEW, SUBMITTED, ACKNOWLEDGED, NOT_APPLICABLE)
# Statuses POST /filings/{id}/status moves to (contract FilingStatusInput.status).
TARGET_STATUSES = (IN_PREPARATION, UNDER_REVIEW, NOT_APPLICABLE)
# Not yet submitted: only these can be overdue or due soon, and only these can still change.
NOT_SUBMITTED = (OPEN, IN_PREPARATION, UNDER_REVIEW)
FINAL = (ACKNOWLEDGED, NOT_APPLICABLE)

# contract Recurrence: a label only; filings are never created from it (PRD open question 3).
RECURRENCES = ("once", "monthly", "quarterly", "half_yearly", "annual")

# Fields of FilingUpdateInput the owner may change (regulatory-reports:filing:prepare), while open or in_preparation.
OWNER_FIELDS = frozenset({"preparation_notes", "links"})
# Fields only regulatory-reports:filing:manage may change, before submission.
MANAGER_FIELDS = frozenset({"owner_id", "due_on", "period_label", "period_start", "period_end"})

# The moves of POST /filings/{id}/status, by (from, to).
START, SEND_FOR_REVIEW, RETURN, MARK_NOT_APPLICABLE = "start", "send_for_review", "return", "not_applicable"
MOVES = {
    (OPEN, IN_PREPARATION): START,
    (IN_PREPARATION, UNDER_REVIEW): SEND_FOR_REVIEW,
    (UNDER_REVIEW, IN_PREPARATION): RETURN,
    (OPEN, NOT_APPLICABLE): MARK_NOT_APPLICABLE,
    (IN_PREPARATION, NOT_APPLICABLE): MARK_NOT_APPLICABLE,
}
# Moves the owner may make with regulatory-reports:filing:prepare; the others need regulatory-reports:filing:manage.
OWNER_MOVES = frozenset({START, SEND_FOR_REVIEW})

# Dates the module accepts anywhere (request bodies and query parameters). The contract sets no range; a statutory
# filing outside these years is a typing mistake, and the bound keeps every date sum far from date.min and date.max.
MIN_DATE, MAX_DATE = date(1900, 1, 1), date(2199, 12, 31)
# Shortest comment or reason (contract FilingStatusInput: minLength 3), counted without surrounding spaces.
MIN_NOTE = 3


def _invalid(code: str, message: str, field: str | None = None) -> DomainRuleError:
    return DomainRuleError(code, message, kind="invalid", field=field)


def _conflict(code: str, message: str, field: str | None = None) -> DomainRuleError:
    return DomainRuleError(code, message, kind="conflict", field=field)


def check_date(value: date, field: str) -> None:
    if not MIN_DATE <= value <= MAX_DATE:
        raise _invalid("date_out_of_range", f"{field} must be between {MIN_DATE} and {MAX_DATE}", field)


def check_period(period_start: date, period_end: date) -> None:
    """422 "period_end before period_start". A one-day period (end == start) is allowed."""
    if period_end < period_start:
        raise _invalid("period_end_before_start", "period_end is before period_start", "period_end")


def check_obligation_active(active: bool) -> None:
    """409: filings are created only for an active obligation."""
    if not active:
        raise _conflict("obligation_inactive", "the obligation is inactive")


def resolve_owner(owner_id: str | None, default_owner_id: str | None) -> str:
    """The owner given, else the obligation's default owner; 422 "no owner" when there is neither."""
    owner = owner_id or default_owner_id
    if not owner:
        raise _invalid("no_owner", "give owner_id or set a default owner on the obligation", "owner_id")
    return owner


def check_editable(status: str, fields: set[str]) -> None:
    """PATCH /filings/{id}: nothing changes once submitted or final (409). Notes and links change only while open or
    in_preparation; owner, due date and period may still change while under review."""
    if status not in NOT_SUBMITTED:
        raise _conflict("filing_read_only", f"a {status} filing cannot be changed")
    if status == UNDER_REVIEW and fields & OWNER_FIELDS:
        field = sorted(fields & OWNER_FIELDS)[0]
        raise _conflict("not_editable_in_status", f"{field} cannot change while the filing is under review", field)


def transition(current: str, target: str) -> str:
    """The move from `current` to `target` (START, SEND_FOR_REVIEW, RETURN or MARK_NOT_APPLICABLE); 409 otherwise."""
    move = MOVES.get((current, target))
    if move is None:
        raise _conflict("transition_not_allowed", f"a {current} filing cannot move to {target}", "status")
    return move


def check_note(move: str, comment: str | None, reason: str | None) -> None:
    """422 when a return has no comment or not_applicable has no reason."""
    if move == RETURN and len((comment or "").strip()) < MIN_NOTE:
        raise _invalid("comment_required", "returning a filing needs a comment", "comment")
    if move == MARK_NOT_APPLICABLE and len((reason or "").strip()) < MIN_NOTE:
        raise _invalid("reason_required", "marking a filing not applicable needs a reason", "reason")


def submit(current: str) -> str:
    if current != UNDER_REVIEW:
        raise _conflict("not_under_review", f"a {current} filing cannot be submitted; it must be under review")
    return SUBMITTED


def acknowledge(current: str) -> str:
    if current != SUBMITTED:
        raise _conflict("not_submitted", f"a {current} filing cannot be acknowledged; it must be submitted")
    return ACKNOWLEDGED


def check_recorded_on(value: date, today: date, field: str, not_before: date | None = None) -> None:
    """submitted_on and acknowledged_on record something that already happened: never after today, and an
    acknowledgement never before the submission (422)."""
    check_date(value, field)
    if value > today:
        raise _invalid("date_in_future", f"{field} is after today", field)
    if not_before is not None and value < not_before:
        raise _invalid("before_submission", f"{field} is before the filing was submitted", field)


def is_overdue(status: str, due_on: date, today: date) -> bool:
    """Not yet submitted and past due_on. A not_applicable filing is never overdue."""
    return status in NOT_SUBMITTED and due_on < today


def is_due_soon(status: str, due_on: date, today: date, due_soon_days: int) -> bool:
    """Not yet submitted and due from today up to due_soon_days ahead. Worked out by subtraction, so no date sum can
    overflow."""
    return status in NOT_SUBMITTED and 0 <= (due_on - today).days <= due_soon_days
