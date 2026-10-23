"""Handlers for the events budget-grants consumes (module.yaml consumes_events). No event bus delivers events to modules
yet, so the host calls `handle(db, name, payload)` for each event it relays. Every handler is idempotent: an entry
from another module is unique by its source, so a repeated event records nothing. Each event runs in a fresh
transaction of its own organisation; handlers refuse to run inside platform_scope."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from eos_core.tenant import is_bypass, organisation_scope
from sqlalchemy.exc import IntegrityError, StatementError
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import ZERO, parse_money
from ..infrastructure.config import load_settings
from ..infrastructure.models import Budget, BudgetHead, Expenditure, Line
from . import service
from .errors import BudgetError
from .service import _q

PO_ISSUED = "procurement.purchase-order.issued"
PO_CANCELLED = "procurement.purchase-order.cancelled"
INVOICE_PAID = "procurement.vendor-invoice.paid"
PAYROLL_PAID = "hr-payroll.payroll-run.paid"


def _ignored(reason: str) -> dict:
    return {"result": "ignored", "reason": reason}


def _exists(db: Session, module: str, reference: str, kind: str) -> bool:
    q = _q(db, Expenditure).where(
        Expenditure.source_module == module, Expenditure.source_reference == reference, Expenditure.kind == kind
    )
    return db.scalar(q) is not None


def _line(db: Session, line_id: str | None) -> Line | None:
    """The line an event names. Spend from another module is recorded even if the line is no longer open: the money
    was really committed or spent, and finance staff must see it."""
    if not line_id:
        return None
    return db.scalar(_q(db, Line).where(Line.id == line_id).with_for_update())


def _day(raw: str | None) -> date:
    return date.fromisoformat(raw[:10]) if raw else service.today()


def _outstanding_commitment(db: Session, purchase_order_id: str, line_id: str) -> Decimal:
    q = _q(db, Expenditure).where(
        Expenditure.purchase_order_id == purchase_order_id,
        Expenditure.line_id == line_id,
        Expenditure.kind == "commitment",
        Expenditure.reversed.is_(False),
    )
    return sum((Decimal(e.amount) for e in db.scalars(q)), ZERO)


def on_po_issued(db: Session, p: dict) -> dict:
    po = p["purchase_order_id"]
    if _exists(db, "procurement", po, "commitment"):
        return _ignored("commitment already recorded")
    line = _line(db, p.get("line_id"))
    if line is None:
        return _ignored("the purchase order names no line of this organisation")
    e = service.record_expenditure(
        db,
        line,
        kind="commitment",
        amount=parse_money(p["total"], "total"),
        day=service.today(),
        description=f"Purchase order {p.get('number') or po}",
        actor_id=None,
        source_module="procurement",
        source_reference=po,
        purchase_order_id=po,
    )
    db.commit()
    return {"result": "committed", "expenditure_id": e.id}


def on_po_cancelled(db: Session, p: dict) -> dict:
    po = p["purchase_order_id"]
    reference = f"{po}/cancelled"
    if _exists(db, "procurement", reference, "commitment"):
        return _ignored("release already recorded")
    line = _line(db, p.get("line_id"))
    if line is None:
        return _ignored("the purchase order names no line of this organisation")
    release = min(parse_money(p["released_amount"], "released_amount"), _outstanding_commitment(db, po, line.id))
    if release <= 0:
        return _ignored("nothing is committed for this purchase order")
    e = service.record_expenditure(
        db,
        line,
        kind="commitment",
        amount=-release,
        day=service.today(),
        description=f"Purchase order {po} released: {p.get('reason') or ''}".strip(": "),
        actor_id=None,
        source_module="procurement",
        source_reference=reference,
        purchase_order_id=po,
    )
    db.commit()
    return {"result": "released", "expenditure_id": e.id, "released": rules.money(release)}


def on_invoice_paid(db: Session, p: dict) -> dict:
    invoice = p["vendor_invoice_id"]
    if _exists(db, "procurement", invoice, "actual"):
        return _ignored("payment already recorded")
    line = _line(db, p.get("line_id"))
    if line is None:
        return _ignored("the invoice names no line of this organisation")
    amount = parse_money(p["amount"])
    day = _day(p.get("paid_on"))
    po = p.get("purchase_order_id")
    # The commitment moves to spent: release what the order still holds, at most the amount paid.
    release = min(amount, _outstanding_commitment(db, po, line.id)) if po else ZERO
    if release > 0:
        service.record_expenditure(
            db,
            line,
            kind="commitment",
            amount=-release,
            day=day,
            description=f"Vendor invoice {invoice} paid",
            actor_id=None,
            source_module="procurement",
            source_reference=invoice,
            purchase_order_id=po,
        )
    e = service.record_expenditure(
        db,
        line,
        kind="actual",
        amount=amount,
        day=day,
        description=f"Vendor invoice {invoice} paid",
        actor_id=None,
        source_module="procurement",
        source_reference=invoice,
        purchase_order_id=po,
    )
    db.commit()
    return {"result": "spent", "expenditure_id": e.id}


def on_payroll_paid(db: Session, p: dict) -> dict:
    run = p["run_id"]
    if _exists(db, "hr-payroll", run, "actual"):
        return _ignored("payroll already recorded")
    settings = load_settings()
    day = _day(p.get("paid_on"))
    year = rules.financial_year_of(day, settings.financial_year_start_month)
    head = db.scalar(_q(db, BudgetHead).where(BudgetHead.code == settings.salary_budget_head_code))
    if head is None:
        return _ignored(f"no budget head {settings.salary_budget_head_code}")
    budget = db.scalar(
        _q(db, Budget).where(Budget.financial_year == year, Budget.department_id.is_(None), Budget.status == "approved")
    )
    if budget is None:
        return _ignored(f"no approved institution-wide budget for {year}")
    line = db.scalar(_q(db, Line).where(Line.budget_id == budget.id, Line.budget_head_id == head.id).with_for_update())
    if line is None:
        return _ignored(f"the {year} budget has no {head.code} line")
    e = service.record_expenditure(
        db,
        line,
        kind="actual",
        amount=parse_money(p["net_total"], "net_total"),
        day=day,
        description=f"Payroll {p.get('period') or run}",
        actor_id=None,
        source_module="hr-payroll",
        source_reference=run,
    )
    db.commit()
    return {"result": "spent", "expenditure_id": e.id}


REQUIRED_IDS = {
    PO_ISSUED: ("purchase_order_id", "line_id"),
    PO_CANCELLED: ("purchase_order_id", "line_id"),
    INVOICE_PAID: ("vendor_invoice_id", "line_id"),
    PAYROLL_PAID: ("run_id",),
}

HANDLERS = {
    PO_ISSUED: on_po_issued,
    PO_CANCELLED: on_po_cancelled,
    INVOICE_PAID: on_invoice_paid,
    PAYROLL_PAID: on_payroll_paid,
}


def handle(db: Session, name: str, payload: dict) -> dict:
    """Apply one consumed event. Unknown names and malformed payloads are ignored with the reason."""
    handler = HANDLERS.get(name)
    if handler is None:
        return _ignored(f"budget-grants does not consume {name}")
    if not isinstance(payload, dict):
        return _ignored("malformed payload: not an object")
    org = payload.get("organisation_id")
    if not org:
        return _ignored("the event carries no organisation_id")
    missing = [k for k in REQUIRED_IDS[name] if not isinstance(payload.get(k), str) or not payload.get(k)]
    if missing:
        return _ignored(f"malformed payload: {', '.join(missing)} must be a non-empty string")
    if is_bypass():
        raise RuntimeError("consumers.handle must not run inside platform_scope")
    db.rollback()  # a fresh transaction, so Postgres row-level security is set for this event's organisation
    with organisation_scope(org):
        try:
            return handler(db, payload)
        except (BudgetError, rules.RuleError) as e:
            db.rollback()
            return _ignored(getattr(e, "message", str(e)))
        except (KeyError, TypeError, ValueError, StatementError) as e:
            db.rollback()
            return _ignored(f"malformed payload: {e}")
        except IntegrityError:
            db.rollback()
            return _ignored("already applied by a concurrent delivery")
        finally:
            db.rollback()
