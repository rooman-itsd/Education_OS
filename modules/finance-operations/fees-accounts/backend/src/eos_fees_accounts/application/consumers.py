"""Handlers for the events fees-accounts consumes (module.yaml consumes_events). No event bus delivers events to modules
yet, so the host calls `handle(db, name, payload)` for each event it relays. Every handler is idempotent: a repeated
event changes nothing and answers why. Each runs inside the event's organisation scope and commits on its own."""

from __future__ import annotations

from datetime import date, timedelta

from eos_core.tenant import organisation_scope
from sqlalchemy.orm import Session

from ..domain import rules
from ..domain.rules import parse_money
from ..infrastructure.config import load_settings
from ..infrastructure.models import FeeHead, FeeStructure, Invoice, Payment, Refund
from . import service
from .errors import FeesError
from .service import _q

PAYMENT_SUCCEEDED = "payment-sbiepay.payment.succeeded"
PAYMENT_FAILED = "payment-sbiepay.payment.failed"
PAYMENT_REFUNDED = "payment-sbiepay.payment.refunded"
APPLICATION_ACCEPTED = "admissions.application.accepted"
ALLOCATION_CONFIRMED = "hostel.allocation.confirmed"
ALLOCATION_CANCELLED = "hostel.allocation.cancelled"
PASS_ISSUED = "transport.pass.issued"
PASS_CANCELLED = "transport.pass.cancelled"
FINE_RAISED = "library.fine.raised"
FINE_WAIVED = "library.fine.waived"


def _ignored(reason: str) -> dict:
    return {"result": "ignored", "reason": reason}


def _done(result: str, **extra) -> dict:
    return {"result": result, **extra}


def _live_from_source(db: Session, module: str, reference: str) -> list[Invoice]:
    q = _q(db, Invoice).where(
        Invoice.source_module == module, Invoice.source_reference == reference, Invoice.status != "cancelled"
    )
    return list(db.scalars(q))


def _published(db: Session, **where) -> FeeStructure | None:
    q = _q(db, FeeStructure).where(FeeStructure.status == "published")
    for key, value in where.items():
        q = q.where(getattr(FeeStructure, key) == value)
    return db.scalar(q.order_by(FeeStructure.published_at.desc()))


def _invoice_all_instalments(db: Session, org: str, structure: FeeStructure, person_id: str, source: dict) -> list[str]:
    numbers = []
    for position in range(1, len(structure.instalments) + 1):
        try:
            inv = service.invoice_from_structure(db, org, structure, position, person_id, None, source)
            numbers.append(inv.number)
        except FeesError as e:
            if e.code != "already_invoiced":
                raise
    return numbers


def _cancel_from_source(db: Session, module: str, reference: str, reason: str) -> dict:
    cancelled, kept = [], []
    for inv in _live_from_source(db, module, reference):
        try:
            service._cancel(db, inv, reason, None)
            cancelled.append(inv.number)
        except FeesError:
            kept.append(inv.number)  # has payments: finance staff refund or keep it
    db.commit()
    if not cancelled and not kept:
        return _ignored(f"no live invoice from {module} {reference}")
    return _done("cancelled", invoices=cancelled, kept_with_payments=kept)


# ---------------------------------------------------------------- payment-sbiepay


def on_payment_succeeded(db: Session, org: str, p: dict) -> dict:
    if p.get("source_module") != service.MODULE:
        return _ignored("not a fees-accounts payment")
    reference = p["reference"]
    if db.scalar(_q(db, Payment).where(Payment.gateway_reference == reference)):
        return _ignored("payment already applied")
    inv = db.scalar(_q(db, Invoice).where(Invoice.id == p["source_reference"]).with_for_update())
    if inv is None:
        return _ignored("invoice not found")
    amount = parse_money(p["amount"])
    completed = p.get("completed_at")
    paid_on = date.fromisoformat(completed[:10]) if completed else service.today()
    # The money is real even if the invoice changed meanwhile (cancelled, or paid at the counter): record it, and a
    # balance below zero shows finance staff what to refund.
    payment = service.apply_payment(
        db, inv, amount=amount, mode="online", paid_on=paid_on, actor_id=None, gateway_reference=reference
    )
    db.commit()
    return _done("applied", payment_id=payment.id, invoice_status=inv.status)


def on_payment_failed(db: Session, org: str, p: dict) -> dict:
    return _ignored("nothing to record: the invoice stays due and the payer may try again")


def on_payment_refunded(db: Session, org: str, p: dict) -> dict:
    if p.get("source_module") != service.MODULE:
        return _ignored("not a fees-accounts payment")
    refund = db.scalar(_q(db, Refund).where(Refund.gateway_refund_id == p.get("refund_id")))
    if refund is None:
        return _ignored("refund not started from fees-accounts")
    if refund.status == "completed":
        return _ignored("refund already completed")
    service.complete_refund(db, refund, None)
    db.commit()
    return _done("completed", refund_id=refund.id)


# ---------------------------------------------------------------- admissions, hostel, transport, library


def on_application_accepted(db: Session, org: str, p: dict) -> dict:
    person_id = p.get("person_id") or p.get("user_id")
    if not person_id:
        return _ignored("the event carries no person id yet (#192)")
    source = {"module": "admissions", "reference": p["application_id"]}
    if _live_from_source(db, "admissions", p["application_id"]):
        return _ignored("already invoiced")
    structure = _published(
        db, applies_to="applicant", academic_year=p.get("academic_year"), programme_id=p.get("programme_id")
    )
    structure = structure or _published(
        db, applies_to="applicant", academic_year=p.get("academic_year"), programme_id=None
    )
    if structure is None:
        return _ignored("no published applicant fee structure for that year and programme")
    inv = service.invoice_from_structure(db, org, structure, 1, person_id, None, source)
    db.commit()
    return _done("invoiced", invoices=[inv.number])


def on_allocation_confirmed(db: Session, org: str, p: dict) -> dict:
    source = {"module": "hostel", "reference": p["allocation_id"]}
    if _live_from_source(db, "hostel", p["allocation_id"]):
        return _ignored("already invoiced")
    structure = _published(db, room_type=p.get("room_type"), academic_year=p.get("academic_year"))
    if structure is None:
        return _ignored("no published fee structure for that room type and year")
    numbers = _invoice_all_instalments(db, org, structure, p["person_id"], source)
    db.commit()
    return _done("invoiced", invoices=numbers)


def on_allocation_cancelled(db: Session, org: str, p: dict) -> dict:
    return _cancel_from_source(
        db, "hostel", p["allocation_id"], f"hostel allocation cancelled: {p.get('reason') or ''}".strip()
    )


def on_pass_issued(db: Session, org: str, p: dict) -> dict:
    if p.get("rider_type") == "staff" and not service.get_settings(db)["invoice_staff_transport"]:
        return _ignored("staff passes are not invoiced (setting invoice_staff_transport)")
    source = {"module": "transport", "reference": p["pass_id"]}
    if _live_from_source(db, "transport", p["pass_id"]):
        return _ignored("already invoiced")
    structure = _published(db, route_id=p.get("route_id"))
    if structure is None:
        return _ignored("no published fee structure for that route")
    numbers = _invoice_all_instalments(db, org, structure, p["person_id"], source)
    db.commit()
    return _done("invoiced", invoices=numbers)


def on_pass_cancelled(db: Session, org: str, p: dict) -> dict:
    return _cancel_from_source(
        db, "transport", p["pass_id"], f"transport pass cancelled: {p.get('reason') or ''}".strip()
    )


def on_fine_raised(db: Session, org: str, p: dict) -> dict:
    if not service.get_settings(db)["invoice_library_fines"]:
        return _ignored("fines are settled at the library desk (setting invoice_library_fines)")
    if _live_from_source(db, "library", p["fine_id"]):
        return _ignored("already invoiced")
    heads = list(db.scalars(_q(db, FeeHead).where(FeeHead.active.is_(True), FeeHead.category.in_(("library", "fine")))))
    head = next((h for h in heads if h.category == "library"), None) or next(iter(heads), None)
    if head is None:
        return _ignored("no active fee head of category library or fine")
    amount = parse_money(p["amount"])
    inv = service.issue_invoice(
        db,
        org,
        person_id=p["person_id"],
        lines=[(head.id, f"Library fine: {p.get('reason') or ''}".strip(": ")[:300], amount)],
        due_date=service.today() + timedelta(days=load_settings().fine_due_days),
        title="Library fine",
        actor_id=None,
        source={"module": "library", "reference": p["fine_id"]},
    )
    db.commit()
    return _done("invoiced", invoices=[inv.number])


def on_fine_waived(db: Session, org: str, p: dict) -> dict:
    return _cancel_from_source(db, "library", p["fine_id"], "library fine waived")


HANDLERS = {
    PAYMENT_SUCCEEDED: on_payment_succeeded,
    PAYMENT_FAILED: on_payment_failed,
    PAYMENT_REFUNDED: on_payment_refunded,
    APPLICATION_ACCEPTED: on_application_accepted,
    ALLOCATION_CONFIRMED: on_allocation_confirmed,
    ALLOCATION_CANCELLED: on_allocation_cancelled,
    PASS_ISSUED: on_pass_issued,
    PASS_CANCELLED: on_pass_cancelled,
    FINE_RAISED: on_fine_raised,
    FINE_WAIVED: on_fine_waived,
}


def handle(db: Session, name: str, payload: dict) -> dict:
    """Apply one consumed event. Unknown names are ignored, so the host can relay every event."""
    handler = HANDLERS.get(name)
    if handler is None:
        return _ignored(f"fees-accounts does not consume {name}")
    org = payload.get("organisation_id")
    if not org:
        return _ignored("the event carries no organisation_id")
    with organisation_scope(org):
        try:
            return handler(db, org, payload)
        except (FeesError, rules.RuleError) as e:
            db.rollback()
            return _ignored(getattr(e, "message", str(e)))
