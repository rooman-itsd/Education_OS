"""Pure procurement rules: exact money and quantities, the purchase method by value, order totals, invoice matching and
masked bank accounts. No database, no framework; amounts are Decimals with two places (the contract's Money is a
decimal string in rupees)."""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
UNIT = Decimal("0.001")
ZERO = Decimal("0.00")
HUNDRED = Decimal("100")
MAX_AMOUNT = Decimal("1000000000000")  # Numeric(14, 2) holds 12 digits before the point
MAX_QUANTITY = Decimal("1000000000")
MAX_TAX_PERCENT = Decimal("100")

VENDOR_STATUSES = ("pending", "approved", "suspended", "blacklisted")
VENDOR_STATUS_CHANGES = ("approved", "suspended", "blacklisted")
INDENT_STATUSES = ("draft", "submitted", "returned", "approved", "rejected", "ordered", "closed")
EDITABLE = ("draft", "returned")
PURCHASE_METHODS = ("direct", "quotation", "tender")
TENDER_METHODS = ("quotation", "tender")
TENDER_STATUSES = ("draft", "published", "closed", "awarded", "cancelled")
PURCHASE_ORDER_STATUSES = (
    "draft",
    "submitted",
    "returned",
    "issued",
    "partially_received",
    "received",
    "closed",
    "cancelled",
)
OPEN_ORDER_STATUSES = ("issued", "partially_received")  # issued and not fully delivered
INVOICEABLE_ORDER_STATUSES = ("issued", "partially_received", "received", "closed")
VENDOR_INVOICE_STATUSES = ("recorded", "approved", "rejected", "paid")
DECISIONS = ("approved", "returned", "rejected")


class RuleError(Exception):
    """A request value breaks a procurement rule. `kind` is "invalid" (422) or "conflict" (409)."""

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


def parse_quantity(value, field: str = "quantity", *, positive: bool = True) -> Decimal:
    """A quantity with at most three decimal places (kg, hours)."""
    try:
        q = Decimal(str(value))
    except (InvalidOperation, TypeError) as e:
        raise RuleError("invalid_quantity", f"{field} must be a number", field=field) from e
    if not q.is_finite() or q != q.quantize(UNIT) or q >= MAX_QUANTITY:
        raise RuleError("invalid_quantity", f"{field} must be a number with at most three decimal places", field=field)
    if (positive and q <= 0) or q < 0:
        raise RuleError(
            "invalid_quantity",
            f"{field} must be greater than zero" if positive else f"{field} cannot be negative",
            field=field,
        )
    return q.quantize(UNIT)


def number(q: Decimal) -> int | float:
    """A quantity as the contract's JSON number: an integer when whole."""
    return int(q) if q == q.to_integral_value() else float(q)


def purchase_method(estimated: Decimal, direct_limit: Decimal | None, quotation_limit: Decimal | None) -> str:
    """Up to the direct limit a direct purchase, up to the quotation limit quotations, above it a tender. The limits
    are the institution's purchase rules with no default (PRD open question 1): without both, nothing is guessed."""
    if direct_limit is None or quotation_limit is None:
        raise RuleError(
            "purchase_limits_not_configured",
            "set PROCUREMENT_DIRECT_PURCHASE_LIMIT and PROCUREMENT_QUOTATION_LIMIT before approving indents",
        )
    if direct_limit > quotation_limit:
        raise RuleError("purchase_limits_not_configured", "the direct purchase limit is above the quotation limit")
    if estimated <= direct_limit:
        return "direct"
    return "quotation" if estimated <= quotation_limit else "tender"


def method_allows(chosen: str, required: str) -> bool:
    """A stricter method than the value requires is allowed; a looser one is not."""
    return PURCHASE_METHODS.index(chosen) >= PURCHASE_METHODS.index(required)


def line_value(item: dict) -> tuple[Decimal, Decimal]:
    """(net, tax) of one priced item, rounded to the paisa."""
    if item.get("unit_price") is None:
        raise RuleError("price_required", "every item of an order needs a unit_price", field="items")
    net = (Decimal(item["quantity"]) * Decimal(item["unit_price"])).quantize(CENT, ROUND_HALF_UP)
    tax = (net * Decimal(item.get("tax_percent") or 0) / HUNDRED).quantize(CENT, ROUND_HALF_UP)
    return net, tax


def order_totals(items: list[dict]) -> tuple[Decimal, Decimal, Decimal]:
    """(subtotal, tax_total, total) of an order's items."""
    subtotal = tax_total = ZERO
    for item in items:
        net, tax = line_value(item)
        subtotal, tax_total = subtotal + net, tax_total + tax
    total = subtotal + tax_total
    if total >= MAX_AMOUNT:
        raise RuleError("invalid_amount", "the order total is too large", field="items")
    return subtotal, tax_total, total


def accepted_value(items: list[dict], accepted: dict[int, Decimal]) -> Decimal:
    """What the accepted quantities are worth at the order's prices, tax included."""
    value = ZERO
    for i, item in enumerate(items):
        qty = accepted.get(i, Decimal(0))
        if qty > 0:
            net, tax = line_value({**item, "quantity": qty})
            value += net + tax
    return value


def within_tolerance(invoiced: Decimal, accepted: Decimal, tolerance_percent: Decimal) -> bool:
    """Everything invoiced on the order stays within the accepted value plus the tolerance."""
    return invoiced <= (accepted * (HUNDRED + tolerance_percent) / HUNDRED).quantize(CENT, ROUND_HALF_UP)


def account_last4(account_number: str) -> str:
    """The only part of a bank account number that is kept: no encryption library is approved yet (decided on #129)."""
    digits = "".join(ch for ch in account_number if not ch.isspace())
    if not digits.isdigit() or not 6 <= len(digits) <= 20:
        raise RuleError("invalid_account_number", "account_number must be 6 to 20 digits", field="bank_account")
    return digits[-4:]
