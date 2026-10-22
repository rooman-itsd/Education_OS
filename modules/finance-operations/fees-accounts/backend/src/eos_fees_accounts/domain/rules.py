"""Pure fee rules: money, instalment splits, late fees, ageing and allocation. No database, no framework; every
amount is an exact Decimal with two places (the contract's Money is a decimal string in rupees)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
ZERO = Decimal("0.00")

FEE_HEAD_CATEGORIES = (
    "admission",
    "tuition",
    "examination",
    "hostel",
    "transport",
    "library",
    "deposit",
    "fine",
    "other",
)
APPLIES_TO = ("applicant", "student")
STRUCTURE_STATUSES = ("draft", "published", "archived")
INVOICE_STATUSES = ("issued", "partially_paid", "paid", "cancelled")
OPEN_INVOICE_STATUSES = ("issued", "partially_paid")
PAYMENT_MODES = ("online", "cash", "cheque", "demand_draft", "bank_transfer")
OFFLINE_MODES = PAYMENT_MODES[1:]
PAYMENT_STATUSES = ("completed", "refunded", "partially_refunded", "void")
REFUND_MODES = ("original", "cash", "cheque", "bank_transfer")
REFUND_STATUSES = ("requested", "completed", "failed")
CONCESSION_KINDS = ("scholarship", "waiver", "staff_ward", "sibling", "other")
CONCESSION_STATUSES = ("requested", "approved", "rejected")
AGEING_BUCKETS = ("not_due", "0-30", "31-60", "61-90", "90+")
LATE_FEE_KINDS = ("flat", "per_day")


class RuleError(Exception):
    """A request value breaks a fee rule. `kind` is "invalid" (422) or "conflict" (409)."""

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
    if positive and amount <= 0:
        raise RuleError("invalid_amount", f"{field} must be greater than zero", field=field)
    if not positive and amount < 0:
        raise RuleError("invalid_amount", f"{field} cannot be negative", field=field)
    return amount.quantize(CENT)


@dataclass(frozen=True)
class Instalment:
    label: str
    percent: Decimal
    due_date: date


def check_instalments(instalments: list[Instalment]) -> None:
    if not instalments:
        raise RuleError("invalid_instalments", "at least one instalment is needed", field="instalments")
    if any(i.percent < 0 or i.percent > 100 for i in instalments):
        raise RuleError("invalid_instalments", "each instalment is between 0 and 100 percent", field="instalments")
    if sum((i.percent for i in instalments), Decimal(0)) != Decimal(100):
        raise RuleError("invalid_instalments", "instalment percentages must add up to 100", field="instalments")


def split_item(amount: Decimal, percents: list[Decimal]) -> list[Decimal]:
    """Share one structure item across instalments. Every share is rounded to the paisa and the last instalment
    takes the remainder, so the shares always add up to the item exactly."""
    shares = [(amount * p / 100).quantize(CENT, ROUND_HALF_UP) for p in percents[:-1]]
    return [*shares, amount - sum(shares, ZERO)]


def instalment_lines(
    items: list[tuple[str, Decimal]], percents: list[Decimal], position: int
) -> list[tuple[str, Decimal]]:
    """(fee_head_id, amount) lines of instalment `position` (1-based); zero lines are left out."""
    if not 1 <= position <= len(percents):
        raise RuleError("invalid_instalment", f"instalment must be between 1 and {len(percents)}", field="instalment")
    lines = [(head, split_item(amount, percents)[position - 1]) for head, amount in items]
    return [(head, amount) for head, amount in lines if amount > 0]


@dataclass(frozen=True)
class LateFeeRule:
    kind: str
    amount: Decimal
    grace_days: int = 0
    cap: Decimal | None = None


def late_fee(rule: LateFeeRule | None, due_date: date, today: date) -> Decimal:
    """The late fee owed today on an unpaid invoice: nothing within the grace days, then a flat amount once, or an
    amount per day late after the grace days, never above the cap."""
    if rule is None:
        return ZERO
    days_late = (today - due_date).days - rule.grace_days
    if days_late <= 0:
        return ZERO
    fee = rule.amount if rule.kind == "flat" else rule.amount * days_late
    if rule.cap is not None:
        fee = min(fee, rule.cap)
    return fee.quantize(CENT)


def balance(total: Decimal, late: Decimal, concessions: Decimal, paid: Decimal) -> Decimal:
    return (total + late - concessions - paid).quantize(CENT)


def invoice_status(current: str, bal: Decimal, paid: Decimal) -> str:
    """Status after a money change. Cancelled stays cancelled; otherwise it follows the balance."""
    if current == "cancelled":
        return current
    if bal <= 0:
        return "paid"
    return "partially_paid" if paid > 0 else "issued"


def is_overdue(status: str, bal: Decimal, due_date: date, today: date) -> bool:
    return status in OPEN_INVOICE_STATUSES and bal > 0 and due_date < today


def ageing_bucket(due_date: date, today: date) -> str:
    days = (today - due_date).days
    if days <= 0:
        return "not_due"
    if days <= 30:
        return "0-30"
    if days <= 60:
        return "31-60"
    if days <= 90:
        return "61-90"
    return "90+"


def allocate(amount: Decimal, weights: list[Decimal]) -> list[Decimal]:
    """Spread `amount` over lines in proportion to `weights` (e.g. a payment over an invoice's fee heads), exact to
    the paisa: the last line takes the remainder."""
    total = sum(weights, ZERO)
    if not weights:
        return []
    if total <= 0:
        return [amount, *([ZERO] * (len(weights) - 1))]
    shares = [(amount * w / total).quantize(CENT, ROUND_HALF_UP) for w in weights[:-1]]
    return [*shares, amount - sum(shares, ZERO)]


def concession_amount(total: Decimal, amount: Decimal | None, percent: Decimal | None) -> Decimal:
    """What a concession is worth: a fixed amount, or a percent of the invoice total. Exactly one is given."""
    if (amount is None) == (percent is None):
        raise RuleError("invalid_concession", "give either amount or percent", field="amount")
    if percent is not None:
        if percent <= 0 or percent > 100:
            raise RuleError("invalid_concession", "percent must be above 0 and at most 100", field="percent")
        return (total * percent / 100).quantize(CENT, ROUND_HALF_UP)
    return amount  # type: ignore[return-value]


def academic_year_of(day: date, start_month: int) -> str:
    """'2026-27' for a day in the academic year that starts in `start_month`."""
    first = day.year if day.month >= start_month else day.year - 1
    return f"{first}-{str(first + 1)[-2:]}"


def academic_year_months(academic_year: str, start_month: int) -> list[str]:
    """The twelve YYYY-MM periods of an academic year such as '2026-27'."""
    try:
        first = int(academic_year.split("-")[0])
    except ValueError as e:
        raise RuleError("invalid_academic_year", "academic_year looks like 2026-27", field="academic_year") from e
    months = []
    for i in range(12):
        m = start_month - 1 + i
        months.append(f"{first + m // 12}-{m % 12 + 1:02d}")
    return months
