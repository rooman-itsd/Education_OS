"""Pure asset-management rules (docs/prd.md sections 5 and 6). No database, no HTTP: plain values in, plain values
out, so every rule is unit-tested on its own."""

from __future__ import annotations

import calendar
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

STATUSES = ("in_service", "in_repair", "idle", "missing", "disposal_pending", "disposed")
MANUAL_STATUSES = ("in_service", "in_repair", "idle", "missing")
IN_DISPOSAL = ("disposal_pending", "disposed")
CONDITIONS = ("new", "good", "fair", "poor", "damaged")
METHODS = ("straight_line", "written_down_value", "none")
DISPOSAL_METHODS = ("sale", "scrap", "donation", "write_off", "transfer_out", "trade_in")
LINE_RESULTS = ("found", "missing", "damaged", "relocated")
CENT = Decimal("0.01")
ZERO = Decimal("0")
DEFAULT_RESIDUAL_PERCENT = 5.0


class RuleViolationError(Exception):
    """A request the rules refuse. status 409 for a wrong state, 422 for invalid input."""

    def __init__(self, code: str, message: str, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def conflict(message: str, code: str = "invalid_state") -> RuleViolationError:
    return RuleViolationError(code, message, status=409)


# ---------------------------------------------------------------- money


def money(amount: str, currency: str, *, allow_negative: bool = False) -> Decimal:
    """Decimal from a contract Money; never a float."""
    try:
        value = Decimal(amount)
    except (InvalidOperation, TypeError) as e:
        raise RuleViolationError("invalid_money", "amount must be a decimal string") from e
    if (value < 0 and not allow_negative) or value != value.quantize(CENT):
        raise RuleViolationError("invalid_money", "amount must be zero or more with at most two decimals")
    if len(currency) != 3 or not currency.isupper():
        raise RuleViolationError("invalid_money", "currency must be a three-letter ISO code")
    return value


def cents(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(value: Decimal) -> str:
    return f"{cents(value)}"


# ---------------------------------------------------------------- dates


def add_months(day: date, months: int) -> date:
    """Calendar months; month ends clamp (31 Jan + 1 month is 28 or 29 Feb)."""
    month0 = day.month - 1 + months
    year, month = day.year + month0 // 12, month0 % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def month_end(day: date) -> date:
    return date(day.year, day.month, calendar.monthrange(day.year, day.month)[1])


def is_month_end(day: date) -> bool:
    return day == month_end(day)


def month_ends(start: date, end: date) -> list[date]:
    """Every month end from the month of start to the month of end, inclusive."""
    out: list[date] = []
    current = month_end(start)
    while current <= month_end(end):
        out.append(current)
        current = month_end(add_months(date(current.year, current.month, 1), 1))
    return out


# ---------------------------------------------------------------- status and transfers (rules 2 and 6)


def check_editable(status: str) -> None:
    if status == "disposed":
        raise conflict("a disposed asset is read-only", "asset_disposed")


def check_manual_status(current: str, new: str) -> None:
    """Disposal statuses change only through a disposal."""
    if current in IN_DISPOSAL:
        raise conflict(
            f"the asset is {current.replace('_', ' ')}; its status changes through the disposal", "in_disposal"
        )
    if new not in MANUAL_STATUSES:
        raise RuleViolationError("invalid_status", f"status must be one of {', '.join(MANUAL_STATUSES)}")


def transfer_changes(current: dict, wanted: dict) -> tuple[dict, dict]:
    """(from, to) for the fields that actually change. At least one must change."""
    keys = [k for k in ("location", "org_unit_id", "custodian_id") if k in wanted and wanted[k] != current.get(k)]
    if not keys:
        raise RuleViolationError("nothing_to_transfer", "give a new location, org_unit_id or custodian_id")
    return {k: current.get(k) for k in keys}, {k: wanted[k] for k in keys}


# ---------------------------------------------------------------- verification (rules 3 and 4)


def next_verification_due(last_verified: date | None, base: date, interval_months: int) -> date:
    """Last verification + the interval; an asset never verified counts from when it went into service."""
    return add_months(last_verified or base, interval_months)


def due_state(due: date | None, today: date, within_days: int) -> str | None:
    """'overdue', 'due_soon' or None."""
    if due is None:
        return None
    if due < today:
        return "overdue"
    if due <= today + timedelta(days=within_days):
        return "due_soon"
    return None


def check_line(result: str, observed_location: str | None) -> None:
    if result not in LINE_RESULTS:
        raise RuleViolationError("invalid_result", f"result must be one of {', '.join(LINE_RESULTS)}")
    if result == "relocated" and not (observed_location or "").strip():
        raise RuleViolationError("location_required", "a relocated asset needs the observed location")


def check_close(pending: int, close_with_pending: bool) -> None:
    if pending and not close_with_pending:
        raise conflict(f"{pending} lines are still pending; decide them or close with pending", "lines_pending")


# ---------------------------------------------------------------- depreciation (rule 5)


@dataclass(frozen=True)
class Depreciation:
    method: str = "none"
    useful_life_months: int | None = None
    rate_percent: float | None = None
    residual_percent: float = DEFAULT_RESIDUAL_PERCENT


def effective_depreciation(category: dict | None, asset: dict | None) -> Depreciation:
    """A value missing on the asset falls back to its category; with neither, nothing is depreciated."""
    merged = {**{k: v for k, v in (category or {}).items() if v is not None}}
    merged.update({k: v for k, v in (asset or {}).items() if v is not None})
    return Depreciation(
        method=merged.get("method", "none"),
        useful_life_months=merged.get("useful_life_months"),
        rate_percent=merged.get("rate_percent"),
        residual_percent=float(merged.get("residual_percent", DEFAULT_RESIDUAL_PERCENT)),
    )


def check_depreciation(d: Depreciation) -> None:
    if d.method not in METHODS:
        raise RuleViolationError("invalid_depreciation", f"method must be one of {', '.join(METHODS)}")
    if d.method == "straight_line" and not d.useful_life_months:
        raise RuleViolationError("invalid_depreciation", "straight_line needs useful_life_months")
    if d.method == "written_down_value" and d.rate_percent is None:
        raise RuleViolationError("invalid_depreciation", "written_down_value needs rate_percent")


def residual_value(cost: Decimal, d: Depreciation) -> Decimal:
    return cents(cost * Decimal(str(d.residual_percent)) / 100)


def monthly_charge(d: Depreciation, cost: Decimal, book_value: Decimal) -> Decimal:
    """One month of depreciation, never taking book value below residual."""
    residual = residual_value(cost, d)
    room = book_value - residual
    if d.method == "none" or room <= 0:
        return ZERO
    if d.method == "straight_line":
        amount = (cost - residual) / Decimal(d.useful_life_months or 1)
    else:
        amount = book_value * Decimal(str(d.rate_percent or 0)) / 100 / 12
    return min(cents(amount), room)


def months_between(start: date, end: date) -> int:
    """Months from the month of start to the month of end, inclusive."""
    return (end.year - start.year) * 12 + end.month - start.month + 1


def straight_line_charge(d: Depreciation, cost: Decimal, book_value: Decimal, n: int) -> Decimal:
    """The n-th month's straight-line charge: the cumulative target after n months less what is already taken, so
    per-month rounding never drifts and the schedule ends exactly at the end of useful life."""
    residual = residual_value(cost, d)
    depreciable = cost - residual
    life = d.useful_life_months or 1
    target = depreciable if n >= life else cents(depreciable * n / life)
    return max(min(target - (cost - book_value), book_value - residual), ZERO)


def first_charge_month(in_service: date) -> date:
    """Pro-rated by month: the month the asset went into service is the first month charged."""
    return month_end(in_service)


def depreciate(
    d: Depreciation, cost: Decimal, book_value: Decimal, in_service: date, months: list[date]
) -> tuple[Decimal, Decimal, list[tuple[date, Decimal, Decimal]]]:
    """Charge the given month ends in order. Returns (total, closing book value, [(month_end, amount, after)])."""
    total = ZERO
    steps: list[tuple[date, Decimal, Decimal]] = []
    start = first_charge_month(in_service)
    for m in months:
        if m < start:
            continue
        if d.method == "straight_line":
            amount = straight_line_charge(d, cost, book_value, months_between(start, m))
        else:
            amount = monthly_charge(d, cost, book_value)
        if amount <= 0:
            break
        book_value -= amount
        total += amount
        steps.append((m, amount, book_value))
    return total, book_value, steps


def project(
    d: Depreciation, cost: Decimal, book_value: Decimal, in_service: date, after: date | None, limit: int = 600
) -> list[tuple[date, Decimal, Decimal]]:
    """The schedule from the month after `after` (or from going into service) until book value reaches residual."""
    first = month_end(add_months(after, 1)) if after else first_charge_month(in_service)
    first = max(first, first_charge_month(in_service))
    months = [month_end(add_months(first, i)) for i in range(limit)]
    return depreciate(d, cost, book_value, in_service, months)[2]


def run_period(period_end: date, last_posted_end: date | None) -> date:
    """A run starts the day after the last posted period, or at the start of its own month."""
    if not is_month_end(period_end):
        raise RuleViolationError("invalid_period", "period_end must be the last day of a month")
    if last_posted_end and period_end <= last_posted_end:
        raise conflict(f"the period up to {last_posted_end.isoformat()} is already posted", "period_posted")
    return last_posted_end + timedelta(days=1) if last_posted_end else date(period_end.year, period_end.month, 1)


# ---------------------------------------------------------------- disposal (rule 6)


def check_disposal_request(status: str) -> None:
    if status in IN_DISPOSAL:
        raise conflict(f"the asset is already {status.replace('_', ' ')}", "in_disposal")


def check_decision(status: str, requested_by: str, decided_by: str) -> None:
    if status != "requested":
        raise conflict("only a requested disposal can be decided", "not_requested")
    if requested_by == decided_by:
        raise conflict("the requester cannot decide their own disposal", "own_request")


def check_cancel(status: str) -> None:
    if status not in ("requested", "approved"):
        raise conflict(f"a {status} disposal cannot be cancelled", "not_open")


def check_complete(status: str) -> None:
    if status != "approved":
        raise conflict("only an approved disposal can be completed", "not_approved")


def tag_for(prefix: str, code: str | None, number: int) -> str:
    """Rule 1: <prefix>-<category code>-<running number>, the code left out when the category has none."""
    return f"{prefix}-{code}-{number:05d}" if code else f"{prefix}-{number:05d}"
