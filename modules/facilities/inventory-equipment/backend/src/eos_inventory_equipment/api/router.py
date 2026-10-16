"""HTTP surface of inventory-equipment, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/inventory-equipment. Handlers only map HTTP to the use cases in application/service.py."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, InventoryError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["inventory-equipment"])

PAGE = Query(1, ge=1)
PAGE_SIZE = Query(50, ge=1, le=200)
UnitStatus = Literal["available", "reserved", "on_loan", "in_repair", "missing", "retired"]
MovementKind = Literal["receipt", "issue", "transfer", "adjustment", "write_off", "loan_out", "loan_return"]


def _run(fn, *args):
    try:
        return fn(*args)
    except InventoryError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- categories and locations


@router.get("/categories")
def list_categories(_: Actor = Depends(require(svc.ITEM_READ)), db: Session = Depends(get_db)):
    return svc.list_categories(db)


@router.post("/categories", status_code=201)
def create_category(body: s.CategoryIn, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_category, db, a, s.dump(body))


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str, body: s.CategoryPatch, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_category, db, a, category_id, s.dump(body, partial=True))


@router.delete("/categories/{category_id}", status_code=204)
def delete_category(category_id: str, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)):
    _run(svc.delete_category, db, a, category_id)
    return Response(status_code=204)


@router.get("/locations")
def list_locations(_: Actor = Depends(require(svc.ITEM_READ)), db: Session = Depends(get_db)):
    return svc.list_locations(db)


@router.post("/locations", status_code=201)
def create_location(body: s.LocationIn, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_location, db, a, s.dump(body))


@router.patch("/locations/{location_id}")
def update_location(
    location_id: str, body: s.LocationPatch, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_location, db, a, location_id, s.dump(body, partial=True))


# ---------------------------------------------------------------- items and units


@router.get("/items")
def list_items(
    category_id: str | None = None,
    tracking: Literal["individual", "quantity"] | None = None,
    loanable: bool | None = None,
    available: bool | None = None,
    q: str | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    _: Actor = Depends(require(svc.ITEM_READ)),
    db: Session = Depends(get_db),
):
    filters = {"category_id": category_id, "tracking": tracking, "loanable": loanable, "available": available, "q": q}
    return svc.list_items(db, filters, page, page_size)


@router.post("/items", status_code=201)
def create_item(body: s.ItemIn, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_item, db, a, s.dump(body))


@router.get("/items/{item_id}")
def get_item(item_id: str, _: Actor = Depends(require(svc.ITEM_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_item, db, item_id)


@router.patch("/items/{item_id}")
def update_item(
    item_id: str, body: s.ItemPatch, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_item, db, a, item_id, s.dump(body, partial=True))


@router.get("/items/{item_id}/units")
def list_units(
    item_id: str,
    status: UnitStatus | None = None,
    _: Actor = Depends(require(svc.ITEM_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_units, db, item_id, status)


@router.post("/items/{item_id}/units", status_code=201)
def register_unit(
    item_id: str, body: s.UnitIn, a: Actor = Depends(require(svc.STOCK_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.register_unit, db, a, item_id, s.dump(body))


@router.get("/units/{unit_id}")
def get_unit(unit_id: str, a: Actor = Depends(require(svc.ITEM_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_unit, db, a, unit_id)


@router.patch("/units/{unit_id}")
def update_unit(
    unit_id: str, body: s.UnitPatch, a: Actor = Depends(require(svc.ITEM_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_unit, db, a, unit_id, s.dump(body, partial=True))


@router.put("/units/{unit_id}/status")
def set_unit_status(
    unit_id: str, body: s.UnitStatusIn, a: Actor = Depends(require(svc.STOCK_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.set_unit_status, db, a, unit_id, s.dump(body))


# ---------------------------------------------------------------- stock


@router.get("/stock")
def list_stock(
    item_id: str | None = None,
    location_id: str | None = None,
    category_id: str | None = None,
    _: Actor = Depends(require(svc.STOCK_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_stock(db, item_id, location_id, category_id)


@router.get("/movements")
def list_movements(
    item_id: str | None = None,
    unit_id: str | None = None,
    location_id: str | None = None,
    kind: MovementKind | None = None,
    from_: datetime | None = Query(None, alias="from"),
    to: datetime | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    _: Actor = Depends(require(svc.STOCK_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "item_id": item_id,
        "unit_id": unit_id,
        "location_id": location_id,
        "kind": kind,
        "from": from_,
        "to": to,
    }
    return svc.list_movements(db, filters, page, page_size)


@router.post("/movements", status_code=201)
def record_movement(body: s.MovementIn, a: Actor = Depends(require(svc.STOCK_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.record_movement, db, a, s.dump(body))


@router.get("/low-stock")
def low_stock(
    category_id: str | None = None, _: Actor = Depends(require(svc.STOCK_READ)), db: Session = Depends(get_db)
):
    return svc.low_stock(db, category_id)


# ---------------------------------------------------------------- loans


@router.get("/loans")
def list_loans(
    scope: Literal["mine", "managed"] = "mine",
    status: str | None = Query(None, description="Comma-separated LoanStatus values"),
    open: bool | None = None,
    borrower_id: str | None = None,
    item_id: str | None = None,
    due_before: datetime | None = None,
    page: int = PAGE,
    page_size: int = PAGE_SIZE,
    a: Actor = Depends(require(svc.LOAN_READ)),
    db: Session = Depends(get_db),
):
    q = {
        "scope": scope,
        "status": [x for x in (status or "").split(",") if x],
        "open": open,
        "borrower_id": borrower_id,
        "item_id": item_id,
        "due_before": due_before,
    }
    return _run(svc.list_loans, db, a, q, page, page_size)


@router.post("/loans", status_code=201)
def request_loan(body: s.LoanIn, a: Actor = Depends(require(svc.LOAN_REQUEST)), db: Session = Depends(get_db)):
    return _run(svc.request_loan, db, a, s.dump(body))


@router.get("/loans/{loan_id}")
def get_loan(loan_id: str, a: Actor = Depends(require(svc.LOAN_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_loan, db, a, loan_id)


@router.post("/loans/{loan_id}/approve")
def approve_loan(
    loan_id: str,
    body: s.NoteIn | None = None,
    a: Actor = Depends(require(svc.LOAN_APPROVE, svc.LOAN_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.decide_loan, db, a, loan_id, True, body.note if body else None)


@router.post("/loans/{loan_id}/reject")
def reject_loan(
    loan_id: str,
    body: s.RequiredReasonIn,
    a: Actor = Depends(require(svc.LOAN_APPROVE, svc.LOAN_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.decide_loan, db, a, loan_id, False, body.reason)


@router.post("/loans/{loan_id}/cancel")
def cancel_loan(
    loan_id: str,
    body: s.ReasonIn | None = None,
    a: Actor = Depends(require(svc.LOAN_REQUEST, svc.LOAN_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_loan, db, a, loan_id, body.reason if body else None)


@router.post("/loans/{loan_id}/hand-out")
def hand_out(
    loan_id: str, body: s.HandOutIn, a: Actor = Depends(require(svc.LOAN_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.hand_out, db, a, loan_id, body.model_dump())


@router.post("/loans/{loan_id}/return")
def return_lines(
    loan_id: str, body: s.ReturnIn, a: Actor = Depends(require(svc.LOAN_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.return_lines, db, a, loan_id, body.model_dump())


@router.post("/loans/{loan_id}/extend")
def extend_loan(
    loan_id: str,
    body: s.ExtendIn,
    a: Actor = Depends(require(svc.LOAN_REQUEST, svc.LOAN_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.extend_loan, db, a, loan_id, body.due_at, body.reason)


@router.post("/loans/{loan_id}/mark-lost")
def mark_lost(
    loan_id: str, body: s.MarkLostIn, a: Actor = Depends(require(svc.LOAN_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.mark_lost, db, a, loan_id, body.line_ids, body.reason)


@router.get("/summary")
def summary(a: Actor = Depends(require(svc.STOCK_READ, svc.LOAN_READ_ALL)), db: Session = Depends(get_db)):
    return svc.summary(db, a)
