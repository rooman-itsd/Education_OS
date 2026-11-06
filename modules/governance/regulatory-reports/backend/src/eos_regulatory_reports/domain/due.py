"""The due statistics behind the widget regulatory-reports.due (GET /stats/due) and the compliance calendar behind
regulatory-reports.compliance-calendar (GET /calendar), PRD "Dashboard widgets"."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .errors import DomainRuleError
from .filings import check_date, is_due_soon, is_overdue

# DueStats.soonest: "Up to ten filings, soonest due first".
SOONEST = 10


@dataclass(frozen=True)
class FilingForDue:
    """What the statistics and the calendar need from a filing."""

    filing_id: str
    obligation_title: str
    authority: str
    period_label: str
    due_on: date
    status: str


@dataclass(frozen=True)
class FilingSummary:
    """Contract FilingSummary, in its field order."""

    filing_id: str
    obligation_title: str
    authority: str
    period_label: str
    due_on: date
    status: str
    overdue: bool


@dataclass(frozen=True)
class DueStats:
    """Contract DueStats, in its field order."""

    scope: str
    due_soon_days: int
    due_soon: int
    overdue: int
    soonest: list[FilingSummary]


def _order(f: FilingForDue) -> tuple:
    return (f.due_on, f.obligation_title, f.period_label, f.filing_id)


def summary(f: FilingForDue, today: date) -> FilingSummary:
    return FilingSummary(
        filing_id=f.filing_id,
        obligation_title=f.obligation_title,
        authority=f.authority,
        period_label=f.period_label,
        due_on=f.due_on,
        status=f.status,
        overdue=is_overdue(f.status, f.due_on, today),
    )


def due_stats(filings: list[FilingForDue], scope: str, due_soon_days: int, today: date) -> DueStats:
    """Counts of the filings not yet submitted that are overdue or due within due_soon_days, and up to ten of them,
    soonest due first (so the longest overdue come first)."""
    overdue = [f for f in filings if is_overdue(f.status, f.due_on, today)]
    soon = [f for f in filings if is_due_soon(f.status, f.due_on, today, due_soon_days)]
    soonest = sorted(overdue + soon, key=_order)[:SOONEST]
    return DueStats(
        scope=scope,
        due_soon_days=due_soon_days,
        due_soon=len(soon),
        overdue=len(overdue),
        soonest=[summary(f, today) for f in soonest],
    )


def check_range(start: date, end: date, max_days: int) -> None:
    """GET /calendar: `to` not before `from` and at most max_days after it (422)."""
    check_date(start, "from")
    check_date(end, "to")
    if end < start:
        raise DomainRuleError("to_before_from", "to is before from", kind="invalid", field="to")
    if (end - start).days > max_days:
        raise DomainRuleError(
            "range_too_long", f"from and to are more than {max_days} days apart", kind="invalid", field="to"
        )


def calendar(filings: list[FilingForDue], start: date, end: date, today: date) -> list[FilingSummary]:
    """Filings due from `start` to `end`, both included, by due date. Every status is shown, so the calendar also
    shows what was filed or marked not applicable."""
    return [summary(f, today) for f in sorted((f for f in filings if start <= f.due_on <= end), key=_order)]
