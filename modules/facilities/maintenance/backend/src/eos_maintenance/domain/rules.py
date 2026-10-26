"""Pure maintenance rules (docs/prd.md sections 5 and 6). No database, no HTTP: plain values in, plain values out,
so every rule is unit-tested on its own."""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

PRIORITIES = ("low", "medium", "high", "urgent")
PRIORITY_RANK = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
OPEN_STATUSES = ("open", "assigned", "in_progress", "on_hold")
FINISHED_STATUSES = ("closed", "cancelled")
HOLD_REASONS = ("waiting_parts", "waiting_vendor", "waiting_access", "other")
TARGET_KINDS = ("asset", "resource", "unit", "location")
INTERVAL_UNITS = ("days", "weeks", "months")


class RuleViolationError(Exception):
    """A request the rules refuse. status 409 for a wrong state, 422 for invalid input."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def conflict(message: str, code: str = "invalid_state") -> RuleViolationError:
    return RuleViolationError(code, message, status=409)


# ---------------------------------------------------------------- SLA (rule 2)


@dataclass(frozen=True)
class SlaHours:
    """Response and resolution targets in hours, per priority."""

    response: dict[str, int] = field(default_factory=dict)
    resolution: dict[str, int] = field(default_factory=dict)


def effective_sla(defaults: SlaHours, override: dict | None) -> SlaHours:
    """Category override wins per priority; missing values come from config."""
    override = override or {}
    return SlaHours(
        response={**defaults.response, **(override.get("response_hours") or {})},
        resolution={**defaults.resolution, **(override.get("resolution_hours") or {})},
    )


def due_times(created_at: datetime, priority: str, sla: SlaHours, held_minutes: int = 0) -> tuple[datetime, datetime]:
    """Response and resolution due times. Time on hold does not count, so it pushes both targets out."""
    paused = timedelta(minutes=held_minutes)
    return (
        created_at + timedelta(hours=sla.response[priority]) + paused,
        created_at + timedelta(hours=sla.resolution[priority]) + paused,
    )


def breaches(
    *,
    status: str,
    now: datetime,
    response_due_at: datetime,
    resolution_due_at: datetime,
    started_at: datetime | None,
    resolved_at: datetime | None,
    flagged: tuple[bool, bool] = (False, False),
) -> list[str]:
    """Which targets are breached: already flagged, or passed now while their timer runs. A timer stops when the
    work starts (response) or is resolved (resolution); nothing runs on hold or after cancellation."""
    out: list[str] = []
    running = status not in ("on_hold", "cancelled")
    response_late = started_at > response_due_at if started_at else running and now > response_due_at
    if flagged[0] or response_late:
        out.append("response")
    resolution_late = (resolved_at > resolution_due_at) if resolved_at else running and now > resolution_due_at
    if flagged[1] or resolution_late:
        out.append("resolution")
    return out


# ---------------------------------------------------------------- lifecycle (section 5)


def initial_status(default_assignee_ids: list[str] | None) -> tuple[str, str | None]:
    """Rule 1: exactly one default assignee sends the ticket straight to assigned."""
    ids = list(default_assignee_ids or [])
    if len(ids) == 1:
        return "assigned", ids[0]
    return "open", None


def check_assign(status: str) -> str:
    """Assign or reassign; returns the new status. An open ticket becomes assigned; others keep their status."""
    if status in ("resolved", *FINISHED_STATUSES):
        raise conflict(f"a {status} ticket cannot be assigned")
    return "assigned" if status == "open" else status


def check_start(status: str, has_assignee: bool) -> str:
    """Start from assigned, or resume from on_hold."""
    if status == "on_hold":
        return "in_progress"
    if status != "assigned" or not has_assignee:
        raise conflict("only an assigned ticket or one on hold can be started", "not_assigned")
    return "in_progress"


def check_hold(status: str, reason: str) -> str:
    if status != "in_progress":
        raise conflict("only a ticket in progress can be put on hold", "not_in_progress")
    if reason not in HOLD_REASONS:
        raise RuleViolationError("invalid_reason", f"hold reason must be one of {', '.join(HOLD_REASONS)}")
    return "on_hold"


def check_resolve(status: str, note: str | None) -> str:
    if status != "in_progress":
        raise conflict("only a ticket in progress can be resolved", "not_in_progress")
    if not (note or "").strip():
        raise RuleViolationError("note_required", "a resolution note is required")
    return "resolved"


def check_close(status: str) -> str:
    if status != "resolved":
        raise conflict("only a resolved ticket can be closed", "not_resolved")
    return "closed"


def check_reopen(status: str, resolved_at: datetime | None, now: datetime, window_days: int) -> None:
    """Rule 5: a resolved or closed ticket can be reopened within the window after it was resolved."""
    if status not in ("resolved", "closed") or resolved_at is None:
        raise conflict("only a resolved or closed ticket can be reopened", "not_resolved")
    if now > resolved_at + timedelta(days=window_days):
        raise conflict(f"the reopen window of {window_days} days has passed", "reopen_window_passed")


def reopen_status(has_assignee: bool) -> str:
    """A reopened ticket goes back to its assignee, or to triage when it never had one."""
    return "assigned" if has_assignee else "open"


def check_cancel(status: str, *, manager: bool) -> str:
    """Rule: not yet resolved. The reporter only before work starts; a manager while it is still open."""
    allowed = OPEN_STATUSES if manager else ("open", "assigned")
    if status not in allowed:
        raise conflict(f"a {status} ticket cannot be cancelled")
    return "cancelled"


def check_editable(status: str) -> None:
    if status in FINISHED_STATUSES:
        raise conflict(f"a {status} ticket cannot be changed", "ticket_finished")


def auto_close_due(resolved_at: datetime, now: datetime, auto_close_days: int) -> bool:
    return now >= resolved_at + timedelta(days=auto_close_days)


# ---------------------------------------------------------------- targets and duplicates


def check_target(kind: str, target_id: str | None, label: str | None) -> None:
    if kind not in TARGET_KINDS:
        raise RuleViolationError("invalid_target", f"target kind must be one of {', '.join(TARGET_KINDS)}")
    if not (label or "").strip():
        raise RuleViolationError("invalid_target", "a target needs a label")
    if kind != "location" and not target_id:
        raise RuleViolationError("invalid_target", f"a {kind} target needs the id from its own module")


def same_target(a: tuple[str, str | None, str], b: tuple[str, str | None, str]) -> bool:
    """Rule 6: same kind and id; locations have no id, so their labels are compared."""
    if a[0] != b[0]:
        return False
    if a[0] == "location":
        return a[2].strip().lower() == b[2].strip().lower()
    return a[1] == b[1]


# ---------------------------------------------------------------- preventive schedules (rule 7)


def add_interval(day: date, every: int, unit: str) -> date:
    """The next due date from the scheduled one, so the plan does not drift. Month ends clamp (31 Jan + 1 month
    is 28 or 29 Feb)."""
    if unit == "days":
        return day + timedelta(days=every)
    if unit == "weeks":
        return day + timedelta(weeks=every)
    if unit != "months":
        raise RuleViolationError("invalid_interval", f"unit must be one of {', '.join(INTERVAL_UNITS)}")
    month0 = day.month - 1 + every
    year, month = day.year + month0 // 12, month0 % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def raise_on(next_due_on: date, lead_days: int) -> date:
    return next_due_on - timedelta(days=lead_days)


def should_raise(*, active: bool, has_open_ticket: bool, next_due_on: date, lead_days: int, today: date) -> bool:
    """A schedule raises its ticket lead_days before the due date, and never has two open tickets at once."""
    return active and not has_open_ticket and today >= raise_on(next_due_on, lead_days)


# ---------------------------------------------------------------- work log and money (rule 9)


def money(amount: str, currency: str) -> Decimal:
    try:
        value = Decimal(amount)
    except (InvalidOperation, TypeError) as e:
        raise RuleViolationError("invalid_money", "amount must be a decimal string") from e
    if value < 0 or value != value.quantize(Decimal("0.01")):
        raise RuleViolationError("invalid_money", "amount must be zero or more with at most two decimals")
    if len(currency) != 3 or not currency.isupper():
        raise RuleViolationError("invalid_money", "currency must be a three-letter ISO code")
    return value


def format_money(value: Decimal) -> str:
    return f"{value.quantize(Decimal('0.01'))}"


def check_work_entry(kind: str, data: dict, *, can_work: bool) -> None:
    """Reporters add notes only; time, parts and costs need maintenance:ticket:work. Each kind needs its field."""
    if kind not in ("note", "time", "part", "cost"):
        raise RuleViolationError("invalid_entry", "kind must be note, time, part or cost")
    if kind != "note" and not can_work:
        raise RuleViolationError("forbidden", "only people who work on the ticket can log time, parts or cost", 403)
    if kind == "note" and not (data.get("note") or "").strip():
        raise RuleViolationError("invalid_entry", "a note needs text")
    if kind == "time" and not (data.get("minutes") or 0) >= 1:
        raise RuleViolationError("invalid_entry", "time needs minutes of at least 1")
    if kind == "part" and not (data.get("item_name") or data.get("item_id")):
        raise RuleViolationError("invalid_entry", "a part needs an item name or an inventory item id")
    if kind == "cost" and not data.get("cost"):
        raise RuleViolationError("invalid_entry", "a cost needs an amount")


def sort_key(priority: str, breached: bool, created_at: datetime) -> tuple:
    """Lists show SLA-breached tickets first, then by priority, oldest first."""
    return (not breached, PRIORITY_RANK.get(priority, 9), created_at)
