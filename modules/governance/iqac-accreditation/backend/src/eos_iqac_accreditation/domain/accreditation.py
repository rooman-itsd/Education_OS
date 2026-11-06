"""Frameworks, cycles, responses and action items (PRD "Main flows", "Statuses" and "Rules"): the statuses, the moves
between them, what may change in each status, and when something is overdue or due soon. Pure Python.

Statuses:
    Cycle:       planning -> collecting -> under_review -> submitted -> closed
    Response:    pending -> submitted -> accepted
                 submitted -> returned -> submitted
    ActionItem:  open -> in_progress -> done
                 open | in_progress -> cancelled
"""

from __future__ import annotations

from datetime import date

from .errors import DomainRuleError

# ---------------------------------------------------------------- statuses (contracts/openapi.yaml)

PLANNING, COLLECTING, UNDER_REVIEW, SUBMITTED_CYCLE, CLOSED = (
    "planning",
    "collecting",
    "under_review",
    "submitted",
    "closed",
)
CYCLE_STATUSES = (PLANNING, COLLECTING, UNDER_REVIEW, SUBMITTED_CYCLE, CLOSED)
# Statuses POST /cycles/{id}/status moves to (contract CycleStatusInput.status).
CYCLE_TARGETS = (COLLECTING, UNDER_REVIEW, SUBMITTED_CYCLE, CLOSED)
CYCLE_MOVES = {
    (PLANNING, COLLECTING),
    (COLLECTING, UNDER_REVIEW),
    (UNDER_REVIEW, SUBMITTED_CYCLE),
    (SUBMITTED_CYCLE, CLOSED),
}
# A framework is "used by an open cycle" while a cycle of it has not been closed.
OPEN_CYCLE = (PLANNING, COLLECTING, UNDER_REVIEW, SUBMITTED_CYCLE)
# Metrics can be assigned in these cycle statuses (contract POST /cycles/{id}/assignments).
ASSIGNABLE = (PLANNING, COLLECTING)
# Responses can be edited and submitted in these cycle statuses (PRD "Rules").
RESPONDING = (COLLECTING, UNDER_REVIEW)

PENDING, SUBMITTED, RETURNED, ACCEPTED = "pending", "submitted", "returned", "accepted"
RESPONSE_STATUSES = (PENDING, SUBMITTED, RETURNED, ACCEPTED)
# The owner may fill in and submit a response in these statuses.
EDITABLE = (PENDING, RETURNED)
# Not yet accepted or in review: only these can be overdue.
AWAITING_OWNER = (PENDING, RETURNED)

OPEN, IN_PROGRESS, DONE, CANCELLED = "open", "in_progress", "done", "cancelled"
ACTION_STATUSES = (OPEN, IN_PROGRESS, DONE, CANCELLED)
# Statuses PATCH /action-items/{id} moves to (contract ActionItemUpdateInput.status).
ACTION_TARGETS = (IN_PROGRESS, DONE, CANCELLED)
ACTION_MOVES = {(OPEN, IN_PROGRESS), (IN_PROGRESS, DONE), (OPEN, CANCELLED), (IN_PROGRESS, CANCELLED)}
# Not finished: only these can be overdue or due soon, and only these can still change.
ACTION_LIVE = (OPEN, IN_PROGRESS)

QUANTITATIVE, QUALITATIVE = "quantitative", "qualitative"
METRIC_KINDS = (QUANTITATIVE, QUALITATIVE)

# Dates the module accepts anywhere (request bodies and query parameters). The contract sets no range; a date outside
# these years is a typing mistake, and the bound keeps every date sum far from date.min and date.max.
MIN_DATE, MAX_DATE = date(1900, 1, 1), date(2199, 12, 31)
# Shortest review comment (contract ReviewInput: minLength 3), counted without surrounding spaces.
MIN_NOTE = 3


def _invalid(code: str, message: str, field: str | None = None) -> DomainRuleError:
    return DomainRuleError(code, message, kind="invalid", field=field)


def _conflict(code: str, message: str, field: str | None = None) -> DomainRuleError:
    return DomainRuleError(code, message, kind="conflict", field=field)


def check_date(value: date, field: str) -> None:
    if not MIN_DATE <= value <= MAX_DATE:
        raise _invalid("date_out_of_range", f"{field} must be between {MIN_DATE} and {MAX_DATE}", field)


# ---------------------------------------------------------------- frameworks and cycles


def check_period(period_start: date, period_end: date) -> None:
    """422 "period_end not after period_start": a cycle covers at least one day."""
    if period_end <= period_start:
        raise _invalid("period_end_not_after_start", "period_end must be after period_start", "period_end")


def check_framework_active(active: bool) -> None:
    """422: a cycle is opened only for an active framework."""
    if not active:
        raise _invalid("framework_inactive", "the framework is inactive", "framework_id")


def check_cycle_planning(status: str) -> None:
    """409: a cycle is renamed or given another period only while planning."""
    if status != PLANNING:
        raise _conflict("cycle_not_planning", f"a {status} cycle can no longer be changed")


def cycle_move(current: str, target: str, submitted_on: date | None, all_accepted: bool) -> None:
    """The move from `current` to `target`. 409 when the move is not one of the four allowed; for submitted, 422
    when submitted_on is missing, then 409 when a response is not accepted."""
    if (current, target) not in CYCLE_MOVES:
        raise _conflict("transition_not_allowed", f"a {current} cycle cannot move to {target}", "status")
    if target == SUBMITTED_CYCLE:
        if submitted_on is None:
            raise _invalid(
                "submitted_on_required", "submitted_on is required to mark a cycle submitted", "submitted_on"
            )
        check_date(submitted_on, "submitted_on")
        if not all_accepted:
            raise _conflict("responses_not_accepted", "every response must be accepted before the cycle is submitted")


def check_assignable(cycle_status: str) -> None:
    if cycle_status not in ASSIGNABLE:
        raise _conflict("cycle_not_assignable", f"metrics cannot be assigned in a {cycle_status} cycle")


def check_metric_assignable(metric_framework_id: str, cycle_framework_id: str, metric_active: bool) -> None:
    """422: only an active metric of the cycle's framework can be assigned."""
    if metric_framework_id != cycle_framework_id:
        raise _invalid("metric_not_in_framework", "the metric is not in the cycle's framework", "metric_id")
    if not metric_active:
        raise _invalid("metric_inactive", "the metric is inactive", "metric_id")


# ---------------------------------------------------------------- responses


def check_cycle_responding(cycle_status: str) -> None:
    if cycle_status not in RESPONDING:
        raise _conflict("cycle_not_collecting", f"responses cannot change in a {cycle_status} cycle")


def check_response_editable(status: str) -> None:
    """409: only the owner's pending or returned response can be saved or submitted."""
    if status not in EDITABLE:
        raise _conflict("response_not_editable", f"a {status} response cannot be changed by its owner")


def check_value_allowed(kind: str, value: float | None) -> None:
    """422: a value belongs to a quantitative metric; a qualitative one has a narrative."""
    if value is not None and kind != QUANTITATIVE:
        raise _invalid("value_not_allowed", "a qualitative metric takes a narrative, not a value", "value")


def check_ready_to_submit(kind: str, value: float | None, narrative: str | None) -> None:
    """422 "value or narrative missing for the metric's kind"."""
    if kind == QUANTITATIVE and value is None:
        raise _invalid("value_required", "a quantitative metric needs a value before it is submitted", "value")
    if kind == QUALITATIVE and not (narrative or "").strip():
        raise _invalid(
            "narrative_required", "a qualitative metric needs a narrative before it is submitted", "narrative"
        )


def check_submitted(status: str) -> None:
    """409: only a submitted response is reviewed."""
    if status != SUBMITTED:
        raise _conflict("response_not_submitted", f"a {status} response cannot be reviewed")


def check_return_comment(comment: str | None) -> None:
    if len((comment or "").strip()) < MIN_NOTE:
        raise _invalid("comment_required", "returning a response needs a comment", "comment")


def check_not_accepted(status: str) -> None:
    """409: evidence of an accepted response is read-only."""
    if status == ACCEPTED:
        raise _conflict("response_accepted", "the response is accepted and can no longer change")


def check_evidence(kind: str, url: str | None, reference: dict | None) -> None:
    """422: a link needs url and nothing else; a reference needs reference and nothing else."""
    if kind == "link" and (url is None or reference is not None):
        raise _invalid("evidence_link_needs_url", "a link needs url, and no reference", "url")
    if kind == "reference" and (reference is None or url is not None):
        raise _invalid("evidence_reference_needs_reference", "a reference needs reference, and no url", "reference")


def is_response_overdue(status: str, due_on: date, today: date) -> bool:
    """Pending or returned and past due_on. A response due today is not overdue."""
    return status in AWAITING_OWNER and due_on < today


# ---------------------------------------------------------------- action items


def check_action_live(status: str) -> None:
    """409: a done or cancelled item cannot change."""
    if status not in ACTION_LIVE:
        raise _conflict("action_item_closed", f"a {status} action item cannot be changed")


def action_move(current: str, target: str) -> None:
    """409 unless open -> in_progress -> done, or open | in_progress -> cancelled. Whether the caller may cancel is
    checked before this."""
    if (current, target) not in ACTION_MOVES:
        raise _conflict("transition_not_allowed", f"a {current} action item cannot move to {target}", "status")


def is_action_overdue(status: str, due_on: date, today: date) -> bool:
    """Open or in progress and past due_on. An item due today is due soon, not overdue."""
    return status in ACTION_LIVE and due_on < today


def is_action_due_soon(status: str, due_on: date, today: date, due_soon_days: int) -> bool:
    """Open or in progress and due from today up to due_soon_days ahead. Worked out by subtraction, so no date sum can
    overflow."""
    return status in ACTION_LIVE and 0 <= (due_on - today).days <= due_soon_days
