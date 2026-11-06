"""HTTP surface of contracts/openapi.yaml mounted at /api/v1/digilocker: the read-only operator view. The Pull
Issuer channels are served by integration-hub's provider-request route, which calls the adapter."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from eos_core.db import get_db, scoped
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import IssuedDocument
from .deps import Principal, require

router = APIRouter(tags=["digilocker"])
MAX_OFFSET = 10_000_000


def _offset(cursor: str | None) -> int:
    """Cursors are opaque to callers; this one is an offset. Anything else is a 400, never a 500."""
    if cursor is None or cursor == "":
        return 0
    if not (cursor.isascii() and cursor.isdigit() and len(cursor) <= 8) or int(cursor) > MAX_OFFSET:
        raise HTTPException(400, {"code": "invalid_cursor", "detail": "invalid cursor"})
    return int(cursor)


@router.get("/issuances")
def list_issuances(
    status: Literal["pushed", "available_for_pull", "pending_holder_account", "withdrawn", "failed"] | None = None,
    doc_kind: str | None = Query(default=None, max_length=40),
    person_id: UUID | None = None,
    cursor: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    p: Principal = Depends(require("digilocker:issuance:read")),
    db: Session = Depends(get_db),
):
    offset = _offset(cursor)
    q = select(IssuedDocument)
    if status:
        q = q.where(IssuedDocument.status == status)
    if doc_kind:
        q = q.where(IssuedDocument.doc_kind == doc_kind)
    if person_id:
        q = q.where(IssuedDocument.person_id == str(person_id))
    q = (
        scoped(db, q, IssuedDocument)
        .order_by(IssuedDocument.created_at.desc(), IssuedDocument.id)
        .offset(offset)
        .limit(limit + 1)
    )
    rows = list(db.scalars(q))
    more = len(rows) > limit
    return {"items": [r.to_dict() for r in rows[:limit]], "next_cursor": str(offset + limit) if more else None}
