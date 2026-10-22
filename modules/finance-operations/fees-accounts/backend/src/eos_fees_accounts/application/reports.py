"""The reports behind the dashboard widgets: collections-today, outstanding-dues and collection-vs-target. Days are UTC
until the organisation's time zone is available to modules."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, money
from ..infrastructure.config import load_settings
from ..infrastructure.models import CollectionTarget, FeeStructure, Invoice, InvoiceLine, Payment
from . import service
from .service import _q, balance_of


def _lines_by_invoice(db: Session, invoice_ids: list[str]) -> dict[str, list[InvoiceLine]]:
    out: dict[str, list[InvoiceLine]] = defaultdict(list)
    if invoice_ids:
        q = _q(db, InvoiceLine).where(InvoiceLine.invoice_id.in_(invoice_ids)).order_by(InvoiceLine.position)
        for line in db.scalars(q):
            out[line.invoice_id].append(line)
    return out


def _by_head(amounts: list[tuple[list[InvoiceLine], Decimal]]) -> list[dict]:
    """Spread each amount over its invoice's fee heads in proportion to the line amounts."""
    totals: dict[str, Decimal] = defaultdict(lambda: ZERO)
    names: dict[str, str] = {}
    for lines, amount in amounts:
        if not lines:
            continue
        for line, share in zip(lines, rules.allocate(amount, [Decimal(x.amount) for x in lines]), strict=True):
            totals[line.fee_head_id] += share
            names[line.fee_head_id] = line.fee_head_name
    ranked = sorted(totals.items(), key=lambda kv: (-kv[1], names[kv[0]]))
    return [{"fee_head_id": head, "name": names[head], "amount": money(amount)} for head, amount in ranked]


def _payments_on(db: Session, day: date) -> list[Payment]:
    """Money received that day; voided payments never counted."""
    q = _q(db, Payment).where(Payment.paid_on == day, Payment.status != "void")
    return list(db.scalars(q))


def collections(db: Session, day: date | None) -> dict:
    day = day or service.today()
    payments = _payments_on(db, day)
    previous = _payments_on(db, day - timedelta(days=1))
    by_mode: dict[str, list[Decimal]] = defaultdict(list)
    for p in payments:
        by_mode[p.mode].append(Decimal(p.amount))
    lines = _lines_by_invoice(db, list({p.invoice_id for p in payments}))
    return {
        "date": day.isoformat(),
        "total": money(sum((Decimal(p.amount) for p in payments), ZERO)),
        "count": len(payments),
        "previous_day_total": money(sum((Decimal(p.amount) for p in previous), ZERO)),
        "by_mode": [
            {"mode": mode, "amount": money(sum(amounts, ZERO)), "count": len(amounts)}
            for mode in rules.PAYMENT_MODES
            if (amounts := by_mode.get(mode))
        ],
        "by_fee_head": _by_head([(lines[p.invoice_id], Decimal(p.amount)) for p in payments]),
    }


def outstanding(db: Session, programme_id: str | None) -> dict:
    now = service.today()
    q = _q(db, Invoice).where(Invoice.status.in_(rules.OPEN_INVOICE_STATUSES))
    if programme_id:
        structures = [s.id for s in db.scalars(_q(db, FeeStructure).where(FeeStructure.programme_id == programme_id))]
        q = q.where(Invoice.fee_structure_id.in_(structures))
    invoices = [i for i in db.scalars(q) if balance_of(i) > 0]
    buckets: dict[str, list[Decimal]] = {b: [] for b in rules.AGEING_BUCKETS}
    for inv in invoices:
        buckets[rules.ageing_bucket(inv.due_date, now)].append(balance_of(inv))
    lines = _lines_by_invoice(db, [i.id for i in invoices])
    return {
        "as_of": now.isoformat(),
        "outstanding": money(sum((balance_of(i) for i in invoices), ZERO)),
        "overdue": money(sum((balance_of(i) for i in invoices if i.due_date < now), ZERO)),
        "people_with_dues": len({i.person_id for i in invoices}),
        "ageing": [
            {"bucket": b, "amount": money(sum(amounts, ZERO)), "count": len(amounts)} for b, amounts in buckets.items()
        ],
        "top_fee_heads": _by_head([(lines[i.id], balance_of(i)) for i in invoices])[:5],
    }


def collection_vs_target(db: Session, academic_year: str | None) -> dict:
    start_month = load_settings().academic_year_start_month
    year = academic_year or rules.academic_year_of(service.today(), start_month)
    months = service._rule(rules.academic_year_months, year, start_month)
    targets = list(db.scalars(_q(db, CollectionTarget).where(CollectionTarget.academic_year == year)))
    overall = defaultdict(lambda: ZERO)
    by_head = defaultdict(lambda: ZERO)
    for t in targets:
        (overall if t.fee_head_id is None else by_head)[t.period] += Decimal(t.amount)
    # An organisation-wide target for a month wins; otherwise the month's per-head targets add up.
    target = {m: overall[m] if m in overall else by_head.get(m, ZERO) for m in months}
    first = date.fromisoformat(f"{months[0]}-01")
    last_month = date.fromisoformat(f"{months[-1]}-01")
    end = date(last_month.year + (last_month.month == 12), last_month.month % 12 + 1, 1)
    q = _q(db, Payment).where(Payment.paid_on >= first, Payment.paid_on < end, Payment.status != "void")
    collected = defaultdict(lambda: ZERO)
    for p in db.scalars(q):
        collected[p.paid_on.strftime("%Y-%m")] += Decimal(p.amount)
    return {
        "academic_year": year,
        "target_total": money(sum(target.values(), ZERO)),
        "collected_total": money(sum(collected.values(), ZERO)),
        "periods": [{"period": m, "target": money(target[m]), "collected": money(collected[m])} for m in months],
    }
