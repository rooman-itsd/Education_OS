"""HTTP surface of contracts/openapi.yaml, mounted at /api/v1/payment-sbiepay."""

from __future__ import annotations

from datetime import date
from typing import Literal

from eos_core.db import get_db, utcnow
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from ..application import service
from ..application.service import PaymentError
from .deps import Principal, current_principal, require

router = APIRouter(tags=["payment-sbiepay"])

AMOUNT = r"^[0-9]+(\.[0-9]{1,2})?$"


def _err(e: PaymentError) -> HTTPException:
    return HTTPException(e.status, str(e))


class Payer(BaseModel):
    person_id: str | None = None
    name: str | None = None
    email: str | None = None
    phone: str | None = None


class PaymentRequest(BaseModel):
    purpose: Literal["subscription", "fee"]
    source_module: str = Field(min_length=1, max_length=60)
    source_reference: str = Field(min_length=1, max_length=100)
    amount: str = Field(pattern=AMOUNT)
    currency: Literal["INR"]
    description: str | None = Field(default=None, max_length=100)
    payer: Payer | None = None
    return_url: str
    notify_url: str | None = None


class RefundRequest(BaseModel):
    amount: str = Field(pattern=AMOUNT)
    reason: str = Field(min_length=1, max_length=300)


class RunRequest(BaseModel):
    settlement_date: date
    report_document_id: str | None = None


class MerchantAccountInput(BaseModel):
    merchant_id: str = Field(min_length=1, max_length=100)
    encryption_key: str | None = None
    mode: Literal["sandbox", "live"]
    active: bool = True


@router.post("/payments", status_code=201)
def start_payment(
    body: PaymentRequest,
    p: Principal = Depends(require("payment-sbiepay:payment:initiate")),
    db: Session = Depends(get_db),
):
    data = body.model_dump()
    data["payer"] = body.payer.model_dump(exclude_none=True) if body.payer else {}
    try:
        session, _ = service.initiate(db, organisation_id=p.organisation_id, user_id=p.user_id, body=data)
    except PaymentError as e:
        if e.status == 409 and e.body:
            return JSONResponse(e.body, status_code=409)
        raise _err(e) from e
    return session


@router.get("/payments")
def list_payments(
    status: str | None = None,
    purpose: str | None = None,
    source_module: str | None = None,
    from_: date | None = Query(default=None, alias="from"),
    to: date | None = None,
    cursor: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    p: Principal = Depends(require("payment-sbiepay:payment:read")),
    db: Session = Depends(get_db),
):
    filters = {"status": status, "purpose": purpose, "source_module": source_module, "from": from_, "to": to}
    try:
        return service.list_payments(db, filters=filters, cursor=cursor, limit=limit)
    except PaymentError as e:
        raise _err(e) from e


@router.get("/payments/{reference}")
def get_payment(reference: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    try:
        payment = service.get_payment(db, reference)
    except PaymentError as e:
        raise _err(e) from e
    if not (p.can("payment-sbiepay:payment:read") or payment.initiated_by == p.user_id):
        raise HTTPException(403, "requires payment-sbiepay:payment:read")
    return payment.to_dict()


@router.get("/payments/{reference}/redirect", response_class=HTMLResponse)
def redirect(reference: str, db: Session = Depends(get_db)):
    try:
        return HTMLResponse(service.redirect_page(db, reference))
    except PaymentError as e:
        raise _err(e) from e


@router.post("/payments/{reference}/verify")
def verify(
    reference: str,
    p: Principal = Depends(require("payment-sbiepay:payment:reconcile")),
    db: Session = Depends(get_db),
):
    try:
        return service.verify(db, reference)
    except PaymentError as e:
        raise _err(e) from e


@router.post("/payments/{reference}/refunds", status_code=202)
def refund(
    reference: str,
    body: RefundRequest,
    p: Principal = Depends(require("payment-sbiepay:payment:refund")),
    db: Session = Depends(get_db),
):
    try:
        return service.refund(db, reference=reference, user_id=p.user_id, amount=body.amount, reason=body.reason)
    except PaymentError as e:
        raise _err(e) from e


@router.post("/callbacks/sbiepay")
async def gateway_callback(request: Request, db: Session = Depends(get_db)):
    form = {k: v for k, v in (await request.form()).items() if isinstance(v, str)}
    try:
        return RedirectResponse(service.handle_callback(db, form), status_code=303)
    except PaymentError as e:
        raise _err(e) from e


@router.get("/reconciliation/summary")
def reconciliation_summary(
    date_: date | None = Query(default=None, alias="date"),
    p: Principal = Depends(require("payment-sbiepay:payment:read")),
    db: Session = Depends(get_db),
):
    return service.summary(db, date_ or utcnow().date())


@router.post("/reconciliation/runs", status_code=202)
def start_run(
    body: RunRequest,
    p: Principal = Depends(require("payment-sbiepay:payment:reconcile")),
    db: Session = Depends(get_db),
):
    try:
        return service.run_reconciliation(
            db,
            organisation_id=p.organisation_id,
            user_id=p.user_id,
            settlement_date=body.settlement_date,
            report_document_id=body.report_document_id,
        )
    except PaymentError as e:
        raise _err(e) from e


@router.get("/reconciliation/runs")
def list_runs(p: Principal = Depends(require("payment-sbiepay:payment:read")), db: Session = Depends(get_db)):
    return service.list_runs(db)


@router.get("/reconciliation/runs/{run_id}")
def get_run(
    run_id: str, p: Principal = Depends(require("payment-sbiepay:payment:read")), db: Session = Depends(get_db)
):
    try:
        return service.get_run(db, run_id)
    except PaymentError as e:
        raise _err(e) from e


@router.get("/merchant-account")
def get_merchant_account(
    p: Principal = Depends(require("payment-sbiepay:merchant-account:manage")), db: Session = Depends(get_db)
):
    try:
        return service.get_merchant_account(db)
    except PaymentError as e:
        raise _err(e) from e


@router.put("/merchant-account")
def put_merchant_account(
    body: MerchantAccountInput,
    p: Principal = Depends(require("payment-sbiepay:merchant-account:manage")),
    db: Session = Depends(get_db),
):
    try:
        return service.put_merchant_account(db, organisation_id=p.organisation_id, body=body.model_dump())
    except PaymentError as e:
        raise _err(e) from e
