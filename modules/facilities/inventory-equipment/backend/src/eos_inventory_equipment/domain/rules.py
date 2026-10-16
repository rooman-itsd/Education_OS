"""Inventory rules: loan rules, stock arithmetic, low-stock crossing and loan status. Pure Python, no framework
or database imports (module standard, backend/src/domain). Every datetime is timezone-aware."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta

TRACKING = ("individual", "quantity")
CONDITIONS = ("new", "good", "fair", "poor", "damaged")
UNIT_STATUSES = ("available", "reserved", "on_loan", "in_repair", "missing", "retired")
SETTABLE_UNIT_STATUSES = ("available", "in_repair", "missing", "retired")  # on_loan / reserved only via loans
LOAN_STATUSES = (
    "requested",
    "approved",
    "rejected",
    "cancelled",
    "on_loan",
    "partially_returned",
    "overdue",
    "returned",
    "closed_with_loss",
)
OPEN_LOAN_STATUSES = frozenset({"requested", "approved", "on_loan", "partially_returned", "overdue"})
OUT_LOAN_STATUSES = frozenset({"on_loan", "partially_returned", "overdue"})
MOVEMENT_KINDS = ("receipt", "issue", "transfer", "adjustment", "write_off", "loan_out", "loan_return")
MANUAL_MOVEMENT_KINDS = ("receipt", "issue", "transfer", "adjustment", "write_off")


class RuleViolationError(Exception):
    """A loan rule forbids this (HTTP 422, contract RuleError)."""

    def __init__(self, code: str, message: str, rule: str | None = None, limit: object = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.rule = rule
        self.limit = limit


class StockShortageError(Exception):
    """Not enough available, or the unit is not available (HTTP 409, contract StockError)."""

    def __init__(self, code: str, message: str, available: float | None = None, requested: float | None = None):
        super().__init__(message)
        self.code = code
        self.message = message
        self.available = available
        self.requested = requested


@dataclass(frozen=True)
class LoanRules:
    """Contract LoanRules after falling back item → category → organisation default."""

    requires_approval: bool = False
    max_loan_days: int = 14
    max_quantity_per_loan: int | None = None
    borrower_role_ids: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        d = asdict(self)
        d["borrower_role_ids"] = list(self.borrower_role_ids)
        return d


def effective_rules(defaults: LoanRules, *layers: dict | None) -> LoanRules:
    """Later layers win; a missing or null value keeps the earlier one."""
    values = asdict(defaults)
    for layer in layers:
        for key, value in (layer or {}).items():
            if key in values and value is not None:
                values[key] = value
    values["borrower_role_ids"] = tuple(values["borrower_role_ids"] or ())
    return LoanRules(**values)


def check_loan_line(
    *, rules: LoanRules, loanable: bool, consumable: bool, active: bool, quantity: float, roles: set[str], manage: bool
) -> None:
    """Raise RuleViolationError if one requested line breaks the item's rules (PRD rules 4 and 11)."""
    if consumable:
        raise RuleViolationError("consumable_not_loanable", "consumables are issued, not lent")
    if not loanable or not active:
        raise RuleViolationError("not_loanable", "this item cannot be borrowed")
    if rules.borrower_role_ids and not roles & set(rules.borrower_role_ids) and not manage:
        raise RuleViolationError("not_loanable", "your role may not borrow this item", "borrower_role_ids")
    if rules.max_quantity_per_loan and quantity > rules.max_quantity_per_loan:
        raise RuleViolationError(
            "too_many_items", "too many of this item in one loan", "max_quantity_per_loan", rules.max_quantity_per_loan
        )


def check_due(due_at: datetime, now: datetime, max_loan_days: int, *, rule: str = "max_loan_days") -> None:
    if due_at <= now:
        raise RuleViolationError("due_in_past", "the due date must be in the future")
    if due_at > now + timedelta(days=max_loan_days):
        raise RuleViolationError("too_long", "the loan would last too long", rule, max_loan_days)


def check_open_loans(open_loans: int, limit: int) -> None:
    if open_loans >= limit:
        raise RuleViolationError(
            "too_many_open_loans", "you already have the most open loans allowed", "max_open_loans_per_person", limit
        )


def take(available: float, requested: float) -> float:
    """Remaining quantity after taking `requested`; stock never goes negative (PRD rule 1)."""
    if requested <= 0:
        raise ValueError("quantity must be positive")
    if requested > available:
        raise StockShortageError("not_enough_stock", "not enough available at this location", available, requested)
    return available - requested


def low_stock_transition(available: float, reorder_level: float | None, currently_low: bool) -> str | None:
    """'low' when available falls to or below the reorder level, 'replenished' when it rises above again,
    None when nothing changed (PRD rule 3: published once per crossing)."""
    if reorder_level is None:
        return "replenished" if currently_low else None
    is_low = available <= reorder_level
    if is_low and not currently_low:
        return "low"
    if not is_low and currently_low:
        return "replenished"
    return None


def loan_status(line_statuses: list[str], due_at: datetime, now: datetime) -> str:
    """Status of a handed-out loan from its lines (PRD section 5)."""
    out = sum(1 for s in line_statuses if s == "out")
    if out == 0:
        return "closed_with_loss" if "lost" in line_statuses else "returned"
    if now > due_at:
        return "overdue"
    return "partially_returned" if out < len(line_statuses) else "on_loan"


def days_late(due_at: datetime, at: datetime) -> int:
    """Whole days late, counting a started day as one."""
    if at <= due_at:
        return 0
    late = at - due_at
    return late.days + (1 if late.seconds or late.microseconds else 0)
