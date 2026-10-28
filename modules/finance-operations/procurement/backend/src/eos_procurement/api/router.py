"""HTTP surface of contracts/openapi.yaml. The host app mounts `router` under /api/v1/procurement. Handlers only map
HTTP to the application layer; errors render as {"detail": {"code", "message", "field"?}}."""

from __future__ import annotations

from typing import Any

from eos_core.db import get_db
from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ..application import access as p
from ..application import reports, service
from ..application.access import Actor
from ..application.errors import ProcurementError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["procurement"])

VENDOR_STATUS = "^(pending|approved|suspended|blacklisted)$"
INDENT_STATUS = "^(draft|submitted|returned|approved|rejected|ordered|closed)$"
TENDER_STATUS = "^(draft|published|closed|awarded|cancelled)$"
ORDER_STATUS = "^(draft|submitted|returned|issued|partially_received|received|closed|cancelled)$"
INVOICE_STATUS = "^(recorded|approved|rejected|paid)$"


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except ProcurementError as e:
        raise HTTPException(e.status, e.body()) from e


Limit = Query(default=50, ge=1, le=200)


def _vendor_body(raw: Any) -> dict:
    """VendorInput, validated here rather than by FastAPI: a validation error never echoes the request back, so a bank
    account number sent with an invalid body does not come back in the 422 (only its last four digits are kept)."""
    try:
        return s.dump(s.VendorInput.model_validate(raw))
    except ValidationError as e:
        errors = [{"type": x["type"], "loc": ["body", *x["loc"]], "msg": x["msg"]} for x in e.errors()]
        raise HTTPException(422, errors) from e


# ---------------------------------------------------------------- vendors


@router.get("/vendors")
def list_vendors(
    status: str | None = Query(default=None, pattern=VENDOR_STATUS),
    category: str | None = None,
    q: str | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.VENDOR_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_vendors, db, status, category, q, cursor, limit)


@router.post("/vendors", status_code=201)
def create_vendor(body: Any = Body(...), a: Actor = Depends(require(p.VENDOR_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.create_vendor, db, a, _vendor_body(body))


@router.get("/vendors/{vendor_id}")
def get_vendor(vendor_id: str, a: Actor = Depends(require(p.VENDOR_READ)), db: Session = Depends(get_db)):
    return _run(service.get_vendor, db, vendor_id)


@router.put("/vendors/{vendor_id}")
def update_vendor(
    vendor_id: str, body: Any = Body(...), a: Actor = Depends(require(p.VENDOR_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.update_vendor, db, a, vendor_id, _vendor_body(body))


@router.post("/vendors/{vendor_id}/status")
def set_vendor_status(
    vendor_id: str,
    body: s.VendorStatusInput,
    a: Actor = Depends(require(p.VENDOR_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.set_vendor_status, db, a, vendor_id, body.status, body.reason)


# ---------------------------------------------------------------- indents


@router.get("/indents")
def list_indents(
    status: str | None = Query(default=None, pattern=INDENT_STATUS),
    department_id: str | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.INDENT_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(service.list_indents, db, status, department_id, cursor, limit)


@router.post("/indents", status_code=201)
def create_indent(body: s.IndentInput, a: Actor = Depends(require(p.INDENT_CREATE)), db: Session = Depends(get_db)):
    return _run(service.create_indent, db, a, s.dump(body))


@router.get("/indents/{indent_id}")
def get_indent(
    indent_id: str, a: Actor = Depends(require(p.INDENT_APPROVE, p.INDENT_CREATE)), db: Session = Depends(get_db)
):
    return _run(service.get_indent, db, a, indent_id, p.INDENT_APPROVE)


@router.put("/indents/{indent_id}")
def update_indent(
    indent_id: str, body: s.IndentInput, a: Actor = Depends(require(p.INDENT_CREATE)), db: Session = Depends(get_db)
):
    return _run(service.update_indent, db, a, indent_id, s.dump(body))


@router.post("/indents/{indent_id}/submit")
def submit_indent(indent_id: str, a: Actor = Depends(require(p.INDENT_CREATE)), db: Session = Depends(get_db)):
    return _run(service.submit_indent, db, a, indent_id)


@router.post("/indents/{indent_id}/decision")
def decide_indent(
    indent_id: str, body: s.Decision, a: Actor = Depends(require(p.INDENT_APPROVE)), db: Session = Depends(get_db)
):
    return _run(service.decide_indent, db, a, indent_id, body.decision, body.note)


@router.get("/me/indents")
def my_indents(a: Actor = Depends(require(p.INDENT_CREATE)), db: Session = Depends(get_db)):
    return _run(service.my_indents, db, a)


# ---------------------------------------------------------------- tenders


@router.get("/tenders")
def list_tenders(
    status: str | None = Query(default=None, pattern=TENDER_STATUS),
    a: Actor = Depends(require(p.TENDER_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.list_tenders, db, status)


@router.post("/tenders", status_code=201)
def create_tender(body: s.TenderInput, a: Actor = Depends(require(p.TENDER_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.create_tender, db, a, s.dump(body))


@router.get("/tenders/{tender_id}")
def get_tender(tender_id: str, a: Actor = Depends(require(p.TENDER_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.get_tender, db, tender_id)


@router.post("/tenders/{tender_id}/publish")
def publish_tender(tender_id: str, a: Actor = Depends(require(p.TENDER_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.publish_tender, db, a, tender_id)


@router.post("/tenders/{tender_id}/quotes", status_code=201)
def record_quote(
    tender_id: str, body: s.QuoteInput, a: Actor = Depends(require(p.TENDER_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.record_quote, db, a, tender_id, s.dump(body))


@router.post("/tenders/{tender_id}/award")
def award_tender(
    tender_id: str, body: s.AwardInput, a: Actor = Depends(require(p.TENDER_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.award_tender, db, a, tender_id, body.quote_id, body.justification)


# ---------------------------------------------------------------- purchase orders and goods receipts


@router.get("/purchase-orders")
def list_orders(
    status: str | None = Query(default=None, pattern=ORDER_STATUS),
    vendor_id: str | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.PURCHASE_ORDER_READ)),
    db: Session = Depends(get_db),
):
    return _run(service.list_orders, db, status, vendor_id, cursor, limit)


@router.post("/purchase-orders", status_code=201)
def create_order(
    body: s.PurchaseOrderInput, a: Actor = Depends(require(p.PURCHASE_ORDER_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.create_order, db, a, s.dump(body))


@router.get("/purchase-orders/{po_id}")
def get_order(po_id: str, a: Actor = Depends(require(p.PURCHASE_ORDER_READ)), db: Session = Depends(get_db)):
    return _run(service.get_order, db, po_id)


@router.put("/purchase-orders/{po_id}")
def update_order(
    po_id: str,
    body: s.PurchaseOrderInput,
    a: Actor = Depends(require(p.PURCHASE_ORDER_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.update_order, db, a, po_id, s.dump(body))


@router.post("/purchase-orders/{po_id}/submit")
def submit_order(po_id: str, a: Actor = Depends(require(p.PURCHASE_ORDER_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.submit_order, db, a, po_id)


@router.post("/purchase-orders/{po_id}/decision")
def decide_order(
    po_id: str, body: s.Decision, a: Actor = Depends(require(p.PURCHASE_ORDER_APPROVE)), db: Session = Depends(get_db)
):
    return _run(service.decide_order, db, a, po_id, body.decision, body.note)


@router.post("/purchase-orders/{po_id}/cancel")
def cancel_order(
    po_id: str,
    body: s.CancelInput,
    a: Actor = Depends(require(p.PURCHASE_ORDER_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(service.cancel_order, db, a, po_id, body.reason)


@router.get("/purchase-orders/{po_id}/goods-receipts")
def list_receipts(po_id: str, a: Actor = Depends(require(p.PURCHASE_ORDER_READ)), db: Session = Depends(get_db)):
    return _run(service.list_receipts, db, po_id)


@router.post("/purchase-orders/{po_id}/goods-receipts", status_code=201)
def record_receipt(
    po_id: str,
    body: s.GoodsReceiptInput,
    a: Actor = Depends(require(p.GOODS_RECEIPT_RECORD)),
    db: Session = Depends(get_db),
):
    return _run(service.record_receipt, db, a, po_id, s.dump(body))


# ---------------------------------------------------------------- vendor invoices


@router.get("/vendor-invoices")
def list_invoices(
    status: str | None = Query(default=None, pattern=INVOICE_STATUS),
    vendor_id: str | None = None,
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.VENDOR_INVOICE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.list_invoices, db, status, vendor_id, cursor, limit)


@router.post("/vendor-invoices", status_code=201)
def record_invoice(
    body: s.VendorInvoiceInput, a: Actor = Depends(require(p.VENDOR_INVOICE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.record_invoice, db, a, s.dump(body))


@router.get("/vendor-invoices/{invoice_id}")
def get_invoice(invoice_id: str, a: Actor = Depends(require(p.VENDOR_INVOICE_MANAGE)), db: Session = Depends(get_db)):
    return _run(service.get_invoice, db, invoice_id)


@router.post("/vendor-invoices/{invoice_id}/decision")
def decide_invoice(
    invoice_id: str,
    body: s.Decision,
    a: Actor = Depends(require(p.VENDOR_INVOICE_APPROVE)),
    db: Session = Depends(get_db),
):
    return _run(service.decide_invoice, db, a, invoice_id, body.decision, body.note)


@router.post("/vendor-invoices/{invoice_id}/mark-paid")
def mark_paid(
    invoice_id: str,
    body: s.MarkPaidInput,
    a: Actor = Depends(require(p.VENDOR_INVOICE_PAY)),
    db: Session = Depends(get_db),
):
    return _run(service.mark_paid, db, a, invoice_id, s.dump(body))


# ---------------------------------------------------------------- reports


@router.get("/reports/purchase-orders-pending")
def purchase_orders_pending(a: Actor = Depends(require(p.REPORT_READ)), db: Session = Depends(get_db)):
    return _run(reports.purchase_orders_pending, db)
