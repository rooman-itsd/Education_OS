"""HTTP surface of library, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/library. Handlers only map HTTP to the use cases in application/service.py; each declares the
permission the contract names for it."""

from __future__ import annotations

from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import service as svc
from ..application.service import Actor, LibraryError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["library"])

LIMIT = Query(20, ge=1, le=100)


def _run(fn, *args):
    try:
        return fn(*args)
    except LibraryError as e:
        raise HTTPException(e.status, e.body()) from e


# ---------------------------------------------------------------- catalogue


@router.get("/titles")
def list_titles(
    q: str | None = None,
    kind: str | None = None,
    available: bool | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.CATALOGUE_READ, svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_titles(db, q, kind, available, cursor, limit)


@router.post("/titles", status_code=201)
def create_title(body: s.TitleIn, a: Actor = Depends(require(svc.CATALOGUE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_title, db, a, s.dump(body))


@router.get("/titles/{title_id}")
def get_title(
    title_id: str, _: Actor = Depends(require(svc.CATALOGUE_READ, svc.SELF_READ)), db: Session = Depends(get_db)
):
    return _run(svc.get_title, db, title_id)


@router.patch("/titles/{title_id}")
def update_title(
    title_id: str, body: s.TitlePatch, a: Actor = Depends(require(svc.CATALOGUE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_title, db, a, title_id, s.dump(body))


@router.post("/titles/{title_id}/copies", status_code=201)
def add_copy(
    title_id: str, body: s.CopyIn, a: Actor = Depends(require(svc.CATALOGUE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.add_copy, db, a, title_id, s.dump(body))


@router.patch("/copies/{copy_id}")
def update_copy(
    copy_id: str, body: s.CopyPatch, a: Actor = Depends(require(svc.CATALOGUE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_copy, db, a, copy_id, s.dump(body))


# ---------------------------------------------------------------- members and policies


@router.get("/members")
def list_members(
    q: str | None = None,
    blocked: bool | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.MEMBER_MANAGE)),
    db: Session = Depends(get_db),
):
    return svc.list_members(db, q, blocked, cursor, limit)


@router.post("/members", status_code=201)
def add_member(body: s.MemberIn, a: Actor = Depends(require(svc.MEMBER_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.add_member, db, a, s.dump(body))


@router.get("/members/{person_id}")
def get_member(person_id: str, _: Actor = Depends(require(svc.MEMBER_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.get_member, db, person_id)


@router.patch("/members/{person_id}")
def update_member(
    person_id: str, body: s.MemberPatch, a: Actor = Depends(require(svc.MEMBER_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_member, db, a, person_id, s.dump(body))


@router.get("/loan-policies")
def list_policies(_: Actor = Depends(require(svc.CATALOGUE_READ)), db: Session = Depends(get_db)):
    return svc.list_policies(db)


@router.put("/loan-policies")
def replace_policies(
    body: list[s.LoanPolicyIn], a: Actor = Depends(require(svc.POLICY_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.replace_policies, db, a, [s.dump(p) for p in body])


# ---------------------------------------------------------------- circulation


@router.get("/loans")
def list_loans(
    status: Literal["active", "returned", "lost"] | None = None,
    overdue: bool | None = None,
    person_id: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.CIRCULATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return svc.list_loans(db, status, overdue, person_id, cursor, limit)


@router.post("/loans", status_code=201)
def issue(body: s.IssueIn, a: Actor = Depends(require(svc.CIRCULATION_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.issue, db, a, body.barcode, body.person_id)


@router.post("/returns")
def return_copy(body: s.ReturnIn, a: Actor = Depends(require(svc.CIRCULATION_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.return_copy, db, a, body.barcode, body.damage_note)


@router.post("/loans/{loan_id}/renew")
def renew(
    loan_id: str, a: Actor = Depends(require(svc.CIRCULATION_MANAGE, svc.SELF_BORROW)), db: Session = Depends(get_db)
):
    return _run(svc.renew, db, a, loan_id)


@router.post("/loans/{loan_id}/lost")
def mark_lost(
    loan_id: str, body: s.LostIn, a: Actor = Depends(require(svc.CIRCULATION_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.mark_lost, db, a, loan_id, body.replacement_amount)


# ---------------------------------------------------------------- reservations


@router.get("/reservations")
def list_reservations(
    status: Literal["waiting", "ready", "fulfilled", "cancelled", "expired"] | None = None,
    title_id: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.CIRCULATION_MANAGE)),
    db: Session = Depends(get_db),
):
    return svc.list_reservations(db, status, title_id, cursor, limit)


@router.post("/reservations/{reservation_id}/cancel")
def cancel_reservation(
    reservation_id: str,
    a: Actor = Depends(require(svc.CIRCULATION_MANAGE, svc.SELF_BORROW)),
    db: Session = Depends(get_db),
):
    return _run(svc.cancel_reservation, db, a, reservation_id)


# ---------------------------------------------------------------- fines


@router.get("/fines")
def list_fines(
    status: Literal["open", "paid", "waived"] | None = None,
    person_id: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    _: Actor = Depends(require(svc.FINE_MANAGE)),
    db: Session = Depends(get_db),
):
    return svc.list_fines(db, status, person_id, cursor, limit)


@router.post("/fines/{fine_id}/pay")
def pay_fine(
    fine_id: str, body: s.ReceiptIn, a: Actor = Depends(require(svc.FINE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.pay_fine, db, a, fine_id, body.receipt_ref)


@router.post("/fines/{fine_id}/waive")
def waive_fine(
    fine_id: str, body: s.ReasonIn, a: Actor = Depends(require(svc.FINE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.waive_fine, db, a, fine_id, body.reason)


# ---------------------------------------------------------------- digital resources


@router.get("/digital-resources")
def list_digital(
    q: str | None = None,
    kind: str | None = None,
    a: Actor = Depends(require(svc.CATALOGUE_READ, svc.SELF_READ)),
    db: Session = Depends(get_db),
):
    return svc.list_digital(db, a, q, kind)


@router.post("/digital-resources", status_code=201)
def create_digital(body: s.DigitalIn, a: Actor = Depends(require(svc.CATALOGUE_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_digital, db, a, s.dump(body))


@router.patch("/digital-resources/{resource_id}")
def update_digital(
    resource_id: str,
    body: s.DigitalPatch,
    a: Actor = Depends(require(svc.CATALOGUE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_digital, db, a, resource_id, s.dump(body))


# ---------------------------------------------------------------- the caller's own (/me)


@router.get("/me/loans")
def my_loans(a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_loans(db, a)


@router.get("/me/reservations")
def my_reservations(a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_reservations(db, a)


@router.post("/me/reservations", status_code=201)
def reserve(body: s.ReserveIn, a: Actor = Depends(require(svc.SELF_BORROW)), db: Session = Depends(get_db)):
    return _run(svc.reserve, db, a, body.title_id)


@router.get("/me/fines")
def my_fines(a: Actor = Depends(require(svc.SELF_READ)), db: Session = Depends(get_db)):
    return svc.my_fines(db, a)
