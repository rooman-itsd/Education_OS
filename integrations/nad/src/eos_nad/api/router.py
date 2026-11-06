"""HTTP surface of contracts/openapi.yaml mounted at /api/v1/nad: the read-only operator view of submissions."""

from __future__ import annotations

from typing import Annotated, Literal
from uuid import UUID

from eos_core.db import get_db, scoped
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..domain.models import STATUSES, Submission, SubmissionFile, iso
from .deps import require

router = APIRouter(tags=["nad"])
MAX_OFFSET = 10_000_000
Status = Literal[STATUSES]  # type: ignore[valid-type]


def _offset(cursor: str | None) -> int:
    """Cursors are opaque to callers; this one is an offset. Anything else is a 400, never a 500."""
    if not cursor:
        return 0
    if not (cursor.isascii() and cursor.isdigit() and len(cursor) <= 8) or int(cursor) > MAX_OFFSET:
        raise HTTPException(400, {"code": "invalid_cursor", "detail": "invalid cursor"})
    return int(cursor)


@router.get("/submissions")
def list_submissions(
    kind: Literal["awards", "award_corrections", "credits"] | None = None,
    status: Status | None = None,
    session: str | None = Query(default=None, pattern=r"^[0-9]{4}-[0-9]{2}$"),
    cursor: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    _=Depends(require("nad:submission:read")),
    db: Session = Depends(get_db),
):
    offset = _offset(cursor)
    q = select(Submission)
    if kind:
        q = q.where(Submission.kind == kind)
    if status:
        q = q.where(Submission.status == status)
    if session:
        q = q.where(Submission.session == session)
    q = scoped(db, q, Submission).order_by(Submission.created_at.desc(), Submission.id).offset(offset).limit(limit + 1)
    rows = list(db.scalars(q))
    more = len(rows) > limit
    return {"items": [r.to_dict() for r in rows[:limit]], "next_cursor": str(offset + limit) if more else None}


@router.get("/submissions/{submission_id}")
def get_submission(
    submission_id: Annotated[UUID, Path()],
    _=Depends(require("nad:submission:read")),
    db: Session = Depends(get_db),
):
    sub = db.scalar(scoped(db, select(Submission).where(Submission.id == str(submission_id)), Submission))
    if sub is None:
        raise HTTPException(404, {"code": "not_found", "detail": "submission not found"})
    files = db.scalars(
        scoped(db, select(SubmissionFile).where(SubmissionFile.submission_id == sub.id), SubmissionFile).order_by(
            SubmissionFile.filename
        )
    )
    return {
        **sub.to_dict(),
        "upload_files": [{"document_id": f.document_id, "filename": f.filename, "rows": f.rows} for f in files],
        "steps": list(sub.steps or []),
        "portal_reference": sub.portal_reference,
        "uploaded_on": iso(sub.uploaded_on),
        "uploaded_by": sub.uploaded_by,
        "row_errors": list(sub.row_errors or []),
    }
