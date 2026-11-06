"""HTTP surface of contracts/openapi.yaml, mounted at /api/v1/video-conferencing: the read-only operator view of
meetings. The provider callbacks of the contract are served by integration-hub at its /inbound routes; the hub asks
the adapter to verify and parse them (application/adapter.py, verify_inbound and parse_inbound), so this router mounts
no callback route. apps/backend does not mount it yet: wiring a router into the host is the host's change."""

from __future__ import annotations

import base64
import binascii
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Annotated

from eos_core.db import get_db, scoped
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from ..infrastructure.models import Attendance, Meeting, Recording, iso
from .deps import Principal, require

READ = "video-conferencing:meeting:read"
CODES = {400: "invalid_request", 401: "unauthenticated", 403: "forbidden", 404: "not_found"}


class _ErrorRoute(APIRoute):
    """Every error leaves as the contract's Error object, {code, detail}."""

    def get_route_handler(self) -> Callable:
        handler = super().get_route_handler()

        async def wrapped(request: Request) -> Response:
            try:
                return await handler(request)
            except HTTPException as e:
                return JSONResponse(
                    {"code": CODES.get(e.status_code, "error"), "detail": str(e.detail)}, e.status_code, e.headers
                )

        return wrapped


router = APIRouter(tags=["video-conferencing"], route_class=_ErrorRoute)


def _decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        if len(cursor) > 200:
            raise ValueError
        when, mid = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        if len(mid) != 36:
            raise ValueError
        return datetime.fromisoformat(when), mid
    except (ValueError, binascii.Error, UnicodeDecodeError):
        raise HTTPException(400, "invalid_cursor") from None


def _encode_cursor(m: Meeting) -> str:
    return base64.urlsafe_b64encode(f"{iso(m.starts_at)}|{m.id}".encode()).decode()


@router.get("/meetings")
def list_meetings(
    provider: Annotated[str | None, Query(pattern="^(zoom|teams|webex|jitsi)$")] = None,
    status: Annotated[str | None, Query(pattern="^(scheduled|started|ended|cancelled)$")] = None,
    caller_module: Annotated[str | None, Query(max_length=60, pattern="^[a-z0-9\\-]+$")] = None,
    from_: Annotated[datetime | None, Query(alias="from")] = None,
    to: datetime | None = None,
    cursor: Annotated[str | None, Query(max_length=200)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    db: Session = Depends(get_db),
    p: Principal = Depends(require(READ)),
):
    q = scoped(db, select(Meeting).where(Meeting.status != "creating"), Meeting)
    for col, value in ((Meeting.provider, provider), (Meeting.status, status), (Meeting.caller_module, caller_module)):
        if value:
            q = q.where(col == value)
    if from_:
        q = q.where(Meeting.starts_at >= (from_ if from_.tzinfo else from_.replace(tzinfo=UTC)))
    if to:
        q = q.where(Meeting.starts_at <= (to if to.tzinfo else to.replace(tzinfo=UTC)))
    if cursor:
        when, mid = _decode_cursor(cursor)
        q = q.where(or_(Meeting.starts_at < when, and_(Meeting.starts_at == when, Meeting.id < mid)))
    rows = db.scalars(q.order_by(Meeting.starts_at.desc(), Meeting.id.desc()).limit(limit + 1)).all()
    page = rows[:limit]
    ids = [m.id for m in page]
    attended = (
        set(db.scalars(select(Attendance.meeting_id).where(Attendance.meeting_id.in_(ids)).distinct()))
        if ids
        else set()
    )
    recs = (
        dict(
            db.execute(
                select(Recording.meeting_id, func.count())
                .where(Recording.meeting_id.in_(ids))
                .group_by(Recording.meeting_id)
            ).all()
        )
        if ids
        else {}
    )
    items = [
        {
            "meeting_key": m.meeting_key, "caller_module": m.caller_module, "provider": m.provider,
            "provider_meeting_id": m.provider_meeting_id, "status": m.status, "starts_at": iso(m.starts_at),
            "duration_minutes": m.duration_minutes, "started_at": iso(m.started_at), "ended_at": iso(m.ended_at),
            "attendance_received": m.id in attended, "recordings": recs.get(m.id, 0),
        }
        for m in page
    ]  # fmt: skip
    return {"items": items, "next_cursor": _encode_cursor(page[-1]) if len(rows) > limit else None}
