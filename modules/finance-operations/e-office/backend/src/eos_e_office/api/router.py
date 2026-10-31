"""HTTP surface of contracts/openapi.yaml. The host app mounts `router` under /api/v1/e-office. Handlers only map HTTP
to the application layer; errors render as {"detail": {"code", "message", "field"?}}."""

from __future__ import annotations

from datetime import date

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..application import access as p
from ..application import reports, service
from ..application.access import Actor
from ..application.errors import EOfficeError
from . import schemas as s
from .deps import require

router = APIRouter(tags=["e-office"])

FILE_STATUS = "^(open|closed)$"
RECEIPT_STATUS = "^(registered|attached)$"
DISPATCH_STATUS = "^(pending|sent)$"


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except EOfficeError as e:
        raise HTTPException(e.status, e.body()) from e


Limit = Query(default=50, ge=1, le=200)


# ---------------------------------------------------------------- categories


@router.get("/categories")
def list_categories(a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)):
    return _run(service.list_categories, db)


@router.post("/categories", status_code=201)
def create_category(
    body: s.CategoryInput, a: Actor = Depends(require(p.SETTINGS_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.create_category, db, a, s.dump(body))


@router.put("/categories/{category_id}")
def update_category(
    category_id: str,
    body: s.CategoryInput,
    a: Actor = Depends(require(p.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.update_category, db, a, category_id, s.dump(body))


# ---------------------------------------------------------------- files


@router.get("/files")
def list_files(
    status: str | None = Query(default=None, pattern=FILE_STATUS),
    category_id: str | None = None,
    department_id: str | None = None,
    holder_id: str | None = None,
    q: str | None = Query(default=None, max_length=200),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.FILE_USE)),
    db: Session = Depends(get_db),
):
    filters = {
        "status": status,
        "category_id": category_id,
        "department_id": department_id,
        "holder_id": holder_id,
        "q": q,
    }
    return _run(service.list_files, db, a, filters, cursor, limit)


@router.post("/files", status_code=201)
def create_file(body: s.FileInput, a: Actor = Depends(require(p.FILE_CREATE)), db: Session = Depends(get_db)):
    return _run(service.create_file, db, a, s.dump(body))


@router.get("/files/{file_id}")
def get_file(file_id: str, a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)):
    return _run(service.get_file, db, a, file_id)


@router.post("/files/{file_id}/notes", status_code=201)
def add_note(file_id: str, body: s.NoteInput, a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)):
    return _run(service.add_note, db, a, file_id, s.dump(body))


@router.post("/files/{file_id}/attachments", status_code=201)
def add_attachment(
    file_id: str, body: s.AttachmentInput, a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)
):
    return _run(service.add_attachment, db, a, file_id, s.dump(body))


@router.post("/files/{file_id}/forward")
def forward_file(
    file_id: str, body: s.ForwardInput, a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)
):
    return _run(service.forward_file, db, a, file_id, s.dump(body))


@router.post("/files/{file_id}/decision")
def decide_file(
    file_id: str, body: s.DecisionInput, a: Actor = Depends(require(p.FILE_DECIDE)), db: Session = Depends(get_db)
):
    return _run(service.decide_file, db, a, file_id, s.dump(body))


@router.post("/files/{file_id}/close")
def close_file(
    file_id: str, body: s.RemarkInput, a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)
):
    return _run(service.close_file, db, a, file_id, body.remark)


@router.post("/files/{file_id}/reopen")
def reopen_file(
    file_id: str, body: s.RemarkInput, a: Actor = Depends(require(p.FILE_CREATE)), db: Session = Depends(get_db)
):
    return _run(service.reopen_file, db, a, file_id, body.remark)


@router.get("/files/{file_id}/movements")
def movements(file_id: str, a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)):
    return _run(service.movements, db, a, file_id)


# ---------------------------------------------------------------- the caller's own


@router.get("/me/inbox")
def inbox(
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.FILE_USE)),
    db: Session = Depends(get_db),
):
    return _run(service.inbox, db, a, cursor, limit)


@router.get("/me/sent")
def sent(
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.FILE_USE)),
    db: Session = Depends(get_db),
):
    return _run(service.sent, db, a, cursor, limit)


@router.get("/me/receipts")
def my_receipts(
    status: str | None = Query(default=None, pattern=RECEIPT_STATUS),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.FILE_USE)),
    db: Session = Depends(get_db),
):
    return _run(service.my_receipts, db, a, status, cursor, limit)


# ---------------------------------------------------------------- inward receipts


@router.get("/receipts")
def list_receipts(
    status: str | None = Query(default=None, pattern=RECEIPT_STATUS),
    day_from: date | None = Query(default=None, alias="from"),
    day_to: date | None = Query(default=None, alias="to"),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.CORRESPONDENCE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.list_receipts, db, status, day_from, day_to, cursor, limit)


@router.post("/receipts", status_code=201)
def register_receipt(
    body: s.ReceiptInput, a: Actor = Depends(require(p.CORRESPONDENCE_MANAGE)), db: Session = Depends(get_db)
):
    return _run(service.register_receipt, db, a, s.dump(body))


@router.get("/receipts/{receipt_id}")
def get_receipt(
    receipt_id: str,
    a: Actor = Depends(require(p.CORRESPONDENCE_MANAGE, p.FILE_USE)),
    db: Session = Depends(get_db),
):
    return _run(service.get_receipt, db, a, receipt_id)


@router.post("/receipts/{receipt_id}/attach")
def attach_receipt(
    receipt_id: str,
    body: s.AttachReceiptInput,
    a: Actor = Depends(require(p.FILE_USE)),
    db: Session = Depends(get_db),
):
    return _run(service.attach_receipt, db, a, receipt_id, body.file_id)


# ---------------------------------------------------------------- outward dispatches


@router.get("/dispatches")
def list_dispatches(
    status: str | None = Query(default=None, pattern=DISPATCH_STATUS),
    cursor: str | None = None,
    limit: int = Limit,
    a: Actor = Depends(require(p.CORRESPONDENCE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.list_dispatches, db, status, cursor, limit)


@router.post("/dispatches", status_code=201)
def request_dispatch(body: s.DispatchInput, a: Actor = Depends(require(p.FILE_USE)), db: Session = Depends(get_db)):
    return _run(service.request_dispatch, db, a, s.dump(body))


@router.post("/dispatches/{dispatch_id}/mark-sent")
def mark_sent(
    dispatch_id: str,
    body: s.MarkSentInput,
    a: Actor = Depends(require(p.CORRESPONDENCE_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(service.mark_sent, db, a, dispatch_id, s.dump(body))


# ---------------------------------------------------------------- reports


@router.get("/reports/pendency")
def pendency(
    department_id: str | None = None,
    a: Actor = Depends(require(p.REPORT_READ)),
    db: Session = Depends(get_db),
):
    return _run(reports.pendency, db, department_id)
