"""Pure hr-payroll rules: exact money, leave days and leave years, carry-forward, payroll periods, the payslip with loss
of pay, and the masked bank account and PAN. No database, no framework; amounts are Decimals with two places (the
contract's Money is a decimal string in rupees) and leave days are Decimals in halves."""

from __future__ import annotations

import calendar
import re
from datetime import date, timedelta
from decimal import ROUND_DOWN, ROUND_HALF_UP, Decimal, InvalidOperation

CENT = Decimal("0.01")
HALF = Decimal("0.5")
ZERO = Decimal("0.00")
MAX_AMOUNT = Decimal("1000000000000")  # Numeric(14, 2) holds 12 digits before the point
MAX_LEAVE_DAYS = Decimal("366")
MAX_PAY_LINES = 50

EMPLOYEE_STATUSES = ("active", "on_notice", "exited")
EMPLOYMENT_TYPES = ("permanent", "contract", "visiting", "part_time")
STAFF_CATEGORIES = ("teaching", "non_teaching")
EXIT_KINDS = ("resignation", "retirement", "termination", "contract_end", "death")
SERVICE_RECORD_KINDS = (
    "joining",
    "confirmation",
    "promotion",
    "transfer",
    "increment",
    "award",
    "disciplinary",
    "training",
    "exit",
    "other",
)
PAY_LINE_KINDS = ("earning", "deduction")
LEAVE_STATUSES = ("pending", "approved", "rejected", "cancelled")
HALF_DAYS = ("none", "first_half", "second_half")
PAYROLL_RUN_STATUSES = ("computing", "review", "submitted", "approved", "paid", "failed")
LOCKED_RUN_STATUSES = ("approved", "paid")  # an approved run is locked; corrections go into a later month
OPEN_RUN_STATUSES = ("computing", "review", "submitted")  # what the dashboard flags late after the due day
APPRAISAL_STATUSES = ("self_review", "manager_review", "completed")
PERIOD = re.compile(r"^([0-9]{4})-([0-9]{2})$")
IFSC = re.compile(r"^[A-Z]{4}0[A-Z0-9]{6}$")
PAN = re.compile(r"^[A-Z]{5}[0-9]{4}[A-Z]$")


class RuleError(Exception):
    """A request value breaks an hr-payroll rule. `kind` is "invalid" (422) or "conflict" (409). The message never
    repeats the value, so a full account number or PAN cannot come back in an error."""

    def __init__(self, code: str, message: str, *, kind: str = "invalid", field: str | None = None) -> None:
        super().__init__(message)
        self.code, self.message, self.kind, self.field = code, message, kind, field


# ---------------------------------------------------------------- money and days


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


def parse_days(value, field: str) -> Decimal:
    """A number of leave days: zero or more, in halves (12, 7.5)."""
    try:
        days = Decimal(str(value))
    except (InvalidOperation, TypeError) as e:
        raise RuleError("invalid_days", f"{field} must be a number of days", field=field) from e
    if not days.is_finite() or days < 0 or days > MAX_LEAVE_DAYS or (days * 2) != (days * 2).to_integral_value():
        raise RuleError("invalid_days", f"{field} must be between 0 and 366 in steps of half a day", field=field)
    return days.quantize(HALF)


def number(q: Decimal) -> int | float:
    """Days as the contract's JSON number: an integer when whole."""
    return int(q) if q == q.to_integral_value() else float(q)


# ---------------------------------------------------------------- bank account and PAN


def account_last4(account_number: str) -> str:
    """The only part of a bank account number that is kept: no encryption library is on the approved stack (decided by
    the owner; see #336). The full number is validated here and then dropped."""
    digits = "".join(ch for ch in account_number if not ch.isspace())
    if not digits.isdigit() or not 6 <= len(digits) <= 20:
        raise RuleError("invalid_account_number", "account_number must be 6 to 20 digits", field="bank_account")
    return digits[-4:]


def check_ifsc(ifsc: str) -> str:
    code = ifsc.strip().upper()
    if not IFSC.match(code):
        raise RuleError(
            "invalid_ifsc",
            "ifsc must be 11 characters: 4 letters, a zero and 6 letters or digits",
            field="bank_account",
        )
    return code


def pan_last4(pan: str) -> str:
    """The last four characters of a PAN, the only part kept (decided by the owner; see #336)."""
    value = pan.strip().upper()
    if not PAN.match(value):
        raise RuleError("invalid_pan", "pan must be 5 letters, 4 digits and a letter", field="pan")
    return value[-4:]


def pan_masked(last4: str | None) -> str | None:
    return None if not last4 else f"XXXXXX{last4}"


# ---------------------------------------------------------------- leave


def leave_days(start: date, end: date, half_day: str = "none") -> Decimal:
    """Calendar days from `start` to `end`, both included; half a day when `half_day` is set. There is no holiday
    calendar in Education OS yet, so weekends and holidays inside a request count (see README, assumptions)."""
    if end < start:
        raise RuleError("invalid_dates", "to cannot be before from", field="to")
    if half_day != "none":
        if start != end:
            raise RuleError("invalid_half_day", "a half day is a single date: from must equal to", field="half_day")
        return HALF
    return Decimal((end - start).days + 1)


def leave_year(day: date, start_month: int) -> int:
    """The leave year a date falls in, named by the calendar year it starts in."""
    return day.year if day.month >= start_month else day.year - 1


def leave_year_bounds(year: int, start_month: int) -> tuple[date, date]:
    first = date(year, start_month, 1)
    following = date(year + 1, start_month, 1)
    return first, following - timedelta(days=1)


def entitlement(days_per_year: Decimal, joined_on: date, year: int, start_month: int) -> Decimal:
    """Days a leave year gives. The year of joining gives a share for the months left in it, the joining month
    included, rounded down to half a day; later years give the full days."""
    first, last = leave_year_bounds(year, start_month)
    if joined_on > last:
        return Decimal(0)
    if joined_on <= first:
        return Decimal(days_per_year)
    months_left = (last.year - joined_on.year) * 12 + last.month - joined_on.month + 1
    share = Decimal(days_per_year) * months_left / 12
    return (share * 2).to_integral_value(ROUND_DOWN) / 2


def carried_into_next_year(entitled: Decimal, carried: Decimal, used: Decimal, carry_forward_max: Decimal) -> Decimal:
    """What is left of a year (unused, never below zero), up to the leave type's carry-forward limit."""
    left = entitled + carried - used
    return max(Decimal(0), min(left, Decimal(carry_forward_max)))


# ---------------------------------------------------------------- payroll


def parse_period(period: str) -> tuple[date, date]:
    """First and last day of a YYYY-MM month."""
    m = PERIOD.match(period or "")
    if not m or not 1 <= int(m.group(2)) <= 12 or int(m.group(1)) < 1900:
        raise RuleError("invalid_period", "period must be a month, YYYY-MM", field="period")
    year, month = int(m.group(1)), int(m.group(2))
    return date(year, month, 1), date(year, month, calendar.monthrange(year, month)[1])


def period_of(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def due_on(period: str, due_day: int) -> date:
    """The day by which the month's run should be approved, kept inside the month (28 in February)."""
    first, last = parse_period(period)
    return first.replace(day=min(max(due_day, 1), last.day))


def employed_days(first: date, last: date, joined_on: date, last_working_day: date | None) -> int:
    """Days of the month the employee was on the rolls: from joining (or the 1st) to the last working day (or the
    month's end), both included."""
    start = max(first, joined_on)
    end = min(last, last_working_day) if last_working_day else last
    return max(0, (end - start).days + 1)


def check_lines(lines: list[dict], field: str = "lines") -> list[dict]:
    """Pay lines as stored: code upper case and unique, kind earning or deduction, amount exact and positive. A
    structure needs an earning, and its deductions cannot exceed its earnings."""
    if not lines:
        raise RuleError("no_earnings", "a salary needs at least one earning line", field=field)
    if len(lines) > MAX_PAY_LINES:
        raise RuleError("too_many_lines", f"at most {MAX_PAY_LINES} lines", field=field)
    out, seen = [], set()
    for n, line in enumerate(lines):
        code = (line.get("code") or "").strip().upper()
        if not code or len(code) > 20:
            raise RuleError(
                "invalid_line_code", "every line needs a code of up to 20 characters", field=f"{field}[{n}]"
            )
        if code in seen:
            raise RuleError("duplicate_line_code", "each code appears once", field=f"{field}[{n}]")
        seen.add(code)
        if line.get("kind") not in PAY_LINE_KINDS:
            raise RuleError("invalid_line_kind", "kind must be earning or deduction", field=f"{field}[{n}]")
        amount = parse_money(line.get("amount"), f"{field}[{n}].amount")
        out.append(
            {
                "code": code,
                "name": (line.get("name") or "").strip() or code,
                "kind": line["kind"],
                "amount": str(amount),
            }
        )
    gross, deductions, _ = totals(out)
    if gross <= 0:
        raise RuleError("no_earnings", "a salary needs at least one earning line", field=field)
    if deductions > gross:
        raise RuleError("deductions_exceed_earnings", "deductions cannot exceed earnings", field=field)
    return out


def totals(lines: list[dict]) -> tuple[Decimal, Decimal, Decimal]:
    """(gross, deductions, net) of pay lines."""
    gross = sum((Decimal(x["amount"]) for x in lines if x["kind"] == "earning"), ZERO)
    deductions = sum((Decimal(x["amount"]) for x in lines if x["kind"] == "deduction"), ZERO)
    return gross, deductions, gross - deductions


def payslip_lines(structure: list[dict], days_in_month: int, paid_days: Decimal) -> list[dict]:
    """The month's lines: every line of the salary structure, earnings and deductions alike, in proportion to the paid
    days, each rounded to the paisa (half up). A full month pays the structure exactly. Statutory deductions are fixed
    lines for now (PRD open question 1), so they follow the paid days as the earnings do."""
    if paid_days >= days_in_month:
        return [dict(x) for x in structure]
    out = []
    for line in structure:
        amount = (Decimal(line["amount"]) * paid_days / Decimal(days_in_month)).quantize(CENT, ROUND_HALF_UP)
        out.append({**line, "amount": str(amount)})
    return out
