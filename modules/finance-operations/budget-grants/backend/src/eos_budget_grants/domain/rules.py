"""Pure budget rules: exact money, availability, thresholds, financial years and certificate due dates. No database,
no framework; every amount is a Decimal with two places (the contract's Money is a decimal string in rupees)."""

from __future__ import annotations

from calendar import monthrange
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_AMOUNT = Decimal("1000000000000")  # Numeric(14, 2) holds 12 digits before the point

HEAD_KINDS = ("recurring", "non_recurring")
BUDGET_STATUSES = ("draft", "submitted", "returned", "approved", "closed")
EDITABLE_BUDGET_STATUSES = ("draft", "returned")
REAPPROPRIATION_STATUSES = ("requested", "approved", "rejected")
EXPENDITURE_KINDS = ("commitment", "actual")
GRANT_STATUSES = ("active", "closed")
INVESTIGATOR_ROLES = ("principal", "co_investigator")
UC_FREQUENCIES = ("yearly", "half_yearly", "on_completion")
UC_STATUSES = ("draft", "returned", "approved", "submitted")
UNSPENT_ACTIONS = ("returned", "carried_over", "none")
REPORT_SCOPES = ("all", "budgets", "grants")


class RuleError(Exception):
    """A request value breaks a budget rule. `kind` is "invalid" (422) or "conflict" (409)."""

    def __init__(self, code: str, message: str, *, kind: str = "invalid", field: str | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.kind, self.field = code, message, kind, field


def money(value: Decimal | str | int | None) -> str | None:
    return None if value is None else f"{Decimal(value).quantize(CENT, ROUND_HALF_UP):.2f}"


def parse_money(value: str | Decimal | int, field: str = "amount", *, positive: bool = True) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError) as e:
        raise RuleError("invalid_amount", f"{field} must be a decimal string in rupees", field=field) from e
    if not amount.is_finite() or amount != amount.quantize(CENT):
        raise RuleError("invalid_amount", f"{field} must have at most two decimal places", field=field)
    if abs(amount) >= MAX_AMOUNT:
        raise RuleError("invalid_amount", f"{field} is too large", field=field)
    if positive and amount <= 0:
        raise RuleError("invalid_amount", f"{field} must be greater than zero", field=field)
    if not positive and amount < 0:
        raise RuleError("invalid_amount", f"{field} cannot be negative", field=field)
    return amount.quantize(CENT)


def available(allocated: Decimal, committed: Decimal, spent: Decimal) -> Decimal:
    """What can still be committed on a line: the allocation less what is committed and spent."""
    return (allocated - committed - spent).quantize(CENT)


def used_percent(allocated: Decimal, committed: Decimal, spent: Decimal) -> Decimal:
    """Committed plus spent as a percentage of the allocation; a line with nothing allocated is 0% until used."""
    used = committed + spent
    if allocated <= 0:
        return Decimal(100) if used > 0 else Decimal(0)
    return used * 100 / allocated


def thresholds_crossed(percent: Decimal, thresholds: list[int]) -> list[int]:
    return [t for t in sorted(thresholds) if percent >= t]


def financial_year_of(day: date, start_month: int) -> str:
    """'2026-27' for a day in the financial year that starts in `start_month` (4 = April)."""
    first = day.year if day.month >= start_month else day.year - 1
    return f"{first}-{str(first + 1)[-2:]}"


def financial_year_bounds(financial_year: str, start_month: int) -> tuple[date, date]:
    """First and last day of a financial year such as '2026-27'."""
    try:
        first = int(financial_year.split("-")[0])
    except ValueError as e:
        raise RuleError("invalid_financial_year", "financial_year looks like 2026-27", field="financial_year") from e
    start = date(first, start_month, 1)
    end_month = start_month - 1 or 12
    end_year = first + 1 if start_month > 1 else first
    return start, date(end_year, end_month, monthrange(end_year, end_month)[1])


def add_months(day: date, months: int) -> date:
    m = day.month - 1 + months
    year, month = day.year + m // 12, m % 12 + 1
    return date(year, month, min(day.day, monthrange(year, month)[1]))


def uc_due_dates(start: date, end: date, frequency: str) -> list[date]:
    """The end of each certificate period: every year or half year from the start (a grant starting 2026-04-01 has
    yearly periods ending 2027-03-31, 2028-03-31...), the last on the end date; or only the end date. A certificate
    whose period ends on such a date covers it."""
    if frequency == "on_completion":
        return [end]
    step = 12 if frequency == "yearly" else 6
    dates, k = [], 1
    while (d := add_months(start, step * k) - timedelta(days=1)) < end:
        dates.append(d)
        k += 1
    return [*dates, end]


def next_uc_due(start: date, end: date, frequency: str, covered_until: date | None) -> date | None:
    """The first due date not yet covered by a certified or submitted certificate (whose period ends on or after it).
    It may be in the past: that certificate is overdue."""
    for due in uc_due_dates(start, end, frequency):
        if covered_until is None or covered_until < due:
            return due
    return None
