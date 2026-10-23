"""HTTP surface of contracts/openapi.yaml. The host app mounts `router` under /api/v1/fees-accounts. Handlers only map
HTTP to the application layer; errors render as {"detail": {"code", "message", "field"?}}."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as p
from ..application import reports, service
from ..application.access import Actor
from ..application.errors import FeesError
from . import schemas as s
from .deps import current_actor, require

router = APIRouter(tags=["fees-accounts"])


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except FeesError as e:
        raise HTTPException(e.status, e.body()) from e


Limit = Query(default=50, ge=1, le=200)


# ---------------------------------------------------------------- fee heads and structures


@router.get("/fee-heads")
def list_fee_heads(
    active: bool | None = None, a: Actor = Depends(require(p.FEE_STRUCTURE_READ)), db: Session = Depends(get_db)
):
    return _run(service.list_fee_heads, db, active)


@router.post("/fee-heads", status_code=201)
def create_fee_head(
    body: s.FeeHeadInput, a: Actor = Depends(require(p.FEE_STRUCTURE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.create_fee_head, db, a, s.dump(body))


@router.put("/fee-heads/{head_id}")
def update_fee_head(
    head_id: str,
    body: s.FeeHeadInput,
    a: Actor = Depends(require(p.FEE_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.update_fee_head, db, a, head_id, s.dump(body))


@router.get("/fee-structures")
def list_structures(
    academic_year: str | None = None,
    programme_id: str | None = None,
    status: str | None = Query(default=None, pattern="^(draft|published|archived)$"),
    a: Actor = Depends(require(p.FEE_STRUCTURE_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_structures, db, academic_year, programme_id, status)


@router.post("/fee-structures", status_code=201)
def create_structure(
    body: s.FeeStructureInput, a: Actor = Depends(require(p.FEE_STRUCTURE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.create_structure, db, a, s.dump(body))


@router.get("/fee-structures/{structure_id}")
def get_structure(structure_id: str, a: Actor = Depends(require(p.FEE_STRUCTURE_READ)), db: Session = Depends(get_db)):
    return _run(service.get_structure, db, structure_id)


@router.put("/fee-structures/{structure_id}")
def update_structure(
    structure_id: str,
    body: s.FeeStructureInput,
    a: Actor = Depends(require(p.FEE_STRUCTURE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.update_structure, db, a, structure_id, s.dump(body))


@router.post("/fee-structures/{structure_id}/publish")
def publish_structure(
    structure_id: str, a: Actor = Depends(require(p.FEE_STRUCTURE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.publish_structure, db, a, structure_id)


@router.post("/fee-structures/{structure_id}/archive")
def archive_structure(
    structure_id: str, a: Actor = Depends(require(p.FEE_STRUCTURE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.archive_structure, db, a, structure_id)


# ---------------------------------------------------------------- invoices


@router.get("/invoices")
def list_invoices(
    person_id: str | None = None,
    status: str | None = Query(default=None, pattern="^(issued|partially_paid|paid|cancelled)$"),
    fee_structure_id: str | None = None,
    overdue: bool | None = None,
    due_from: date | None = None,
    due_to: date | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.INVOICE_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "person_id": person_id,
        "status": status,
        "fee_structure_id": fee_structure_id,
        "overdue": overdue,
        "due_from": due_from,
        "due_to": due_to,
    }
    return _run(service.list_invoices, db, filters, cursor, limit)


@router.post("/invoices", status_code=201)
def create_invoice(body: s.InvoiceInput, a: Actor = Depends(require(p.INVOICE_CREATE)), db: Session = Depends(get_db)):
    return _run(service.create_invoice, db, a, s.dump(body))


@router.post("/invoices/bulk", status_code=202)
def bulk_invoices(
    body: s.BulkInvoiceInput, a: Actor = Depends(require(p.INVOICE_CREATE)), db: Session = Depends(get_db)
):
    return _run(service.bulk_invoices, db, a, s.dump(body))


@router.get("/invoices/bulk/{job_id}")
def get_bulk(job_id: str, a: Actor = Depends(require(p.INVOICE_CREATE)), db: Session = Depends(get_db)):
    return _run(service.get_bulk, db, job_id)


@router.get("/invoices/{invoice_id}")
def get_invoice(invoice_id: str, a: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return _run(service.get_invoice, db, a, invoice_id)


@router.post("/invoices/{invoice_id}/cancel")
def cancel_invoice(
    invoice_id: str, body: s.Reason, a: Actor = Depends(require(p.INVOICE_CANCEL)), db: Session = Depends(get_db)
):
    return _run(service.cancel_invoice, db, a, invoice_id, body.reason)


@router.post("/invoices/{invoice_id}/pay", status_code=201)
def pay_invoice(
    invoice_id: str,
    body: s.PayInput | None = None,
    a: Actor = Depends(require(p.SELF_PAY)),
    db: Session = Depends(get_db),
):
    return _run(service.pay_online, db, a, invoice_id, s.dump(body) if body else {})


@router.post("/invoices/{invoice_id}/payments", status_code=201)
def record_payment(
    invoice_id: str,
    body: s.OfflinePaymentInput,
    a: Actor = Depends(require(p.PAYMENT_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(service.record_offline_payment, db, a, invoice_id, s.dump(body))


# ---------------------------------------------------------------- payments, refunds, receipts


@router.get("/payments")
def list_payments(
    person_id: str | None = None,
    mode: str | None = Query(default=None, pattern="^(online|cash|cheque|demand_draft|bank_transfer)$"),
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.INVOICE_READ)),
    db: Session = Depends(get_db),
):
    filters = {"person_id": person_id, "mode": mode, "from": from_, "to": to}
    return _run(service.list_payments, db, filters, cursor, limit)


@router.get("/payments/{payment_id}")
def get_payment(payment_id: str, a: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return _run(service.get_payment, db, a, payment_id)


@router.post("/payments/{payment_id}/refunds", status_code=202)
def refund_payment(
    payment_id: str, body: s.RefundInput, a: Actor = Depends(require(p.PAYMENT_REFUND)), db: Session = Depends(get_db)
):
    return _run(service.refund_payment, db, a, payment_id, s.dump(body))


@router.post("/payments/{payment_id}/void")
def void_payment(
    payment_id: str, body: s.Reason, a: Actor = Depends(require(p.PAYMENT_REFUND)), db: Session = Depends(get_db)
):
    return _run(service.void_payment, db, a, payment_id, body.reason)


@router.get("/receipts/{receipt_id}")
def get_receipt(receipt_id: str, a: Actor = Depends(current_actor), db: Session = Depends(get_db)):
    return _run(service.get_receipt, db, a, receipt_id)


# ---------------------------------------------------------------- concessions


@router.get("/concessions")
def list_concessions(
    person_id: str | None = None,
    status: str | None = Query(default=None, pattern="^(requested|approved|rejected)$"),
    a: Actor = Depends(require(p.CONCESSION_REQUEST, p.CONCESSION_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(service.list_concessions, db, person_id, status)


@router.post("/concessions", status_code=201)
def request_concession(
    body: s.ConcessionInput, a: Actor = Depends(require(p.CONCESSION_REQUEST)), db: Session = Depends(get_db)
):
    return _run(service.request_concession, db, a, s.dump(body))


@router.post("/concessions/{concession_id}/decision")
def decide_concession(
    concession_id: str,
    body: s.ConcessionDecision,
    a: Actor = Depends(require(p.CONCESSION_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(service.decide_concession, db, a, concession_id, body.decision, body.note)


# ---------------------------------------------------------------- ledgers, self service, dues


@router.get("/accounts/{person_id}/statement")
def statement(
    person_id: str,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    a: Actor = Depends(require(p.LEDGER_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.statement, db, person_id, from_, to)


@router.get("/me/dues")
def my_dues(a: Actor = Depends(require(p.SELF_READ)), db: Session = Depends(get_db)):
    return _run(service.my_dues, db, a)


@router.get("/me/invoices")
def my_invoices(
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.my_invoices, db, a, cursor, limit)


@router.get("/me/receipts")
def my_receipts(a: Actor = Depends(require(p.SELF_READ)), db: Session = Depends(get_db)):
    return _run(service.my_receipts, db, a)


@router.get("/dues")
def dues(
    person_id: str,
    source_module: str | None = None,
    source_reference: str | None = None,
    a: Actor = Depends(require(p.DUES_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.dues, db, person_id, source_module, source_reference)


# ---------------------------------------------------------------- settings, targets, reports


@router.get("/settings")
def get_settings(a: Actor = Depends(require(p.FEE_STRUCTURE_READ)), db: Session = Depends(get_db)):
    return _run(service.get_settings, db)


@router.put("/settings")
def put_settings(
    body: s.SettingsInput, a: Actor = Depends(require(p.FEE_STRUCTURE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.put_settings, db, a, s.dump(body))


@router.get("/collection-targets")
def list_targets(
    academic_year: str | None = None, a: Actor = Depends(require(p.REPORT_READ)), db: Session = Depends(get_db)
):
    return _run(service.list_targets, db, academic_year)


@router.put("/collection-targets")
def put_targets(body: s.TargetsInput, a: Actor = Depends(require(p.TARGET_MANAGE)), db: Session = Depends(get_db)):
    data = s.dump(body)
    return _run(service.put_targets, db, a, data["academic_year"], data["targets"])


@router.get("/reports/collections")
def collections_report(
    date_: date | None = Query(default=None, alias="date"),
    a: Actor = Depends(require(p.REPORT_READ)),
    db: Session = Depends(get_db),
):
    return _run(reports.collections, db, date_)


@router.get("/reports/outstanding")
def outstanding_report(
    programme_id: str | None = None, a: Actor = Depends(require(p.REPORT_READ)), db: Session = Depends(get_db)
):
    return _run(reports.outstanding, db, programme_id)


@router.get("/reports/collection-vs-target")
def collection_vs_target_report(
    academic_year: str | None = None, a: Actor = Depends(require(p.REPORT_READ)), db: Session = Depends(get_db)
):
    return _run(reports.collection_vs_target, db, academic_year)
