"""HTTP surface of contracts/openapi.yaml, mounted at /api/v1/wearables: the coach's device alerts. The provider callbacks of
the contract are served by integration-hub at its /inbound routes; the hub asks the adapter to verify and parse them
(application/adapter.py, verify_inbound and parse_inbound), so this router mounts no callback route. apps/backend does not
mount it yet: wiring a router into the host is the host's change."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated
from uuid import UUID

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from sqlalchemy.orm import Session

from ..application import alerts as alerts_service
from ..infrastructure.config import Config
from ..infrastructure.providers.base import utcnow
from .deps import Principal, require

READ = "wearables:alert:read"
CODES = {400: "invalid_request", 401: "unauthenticated", 403: "forbidden", 404: "not_found"}
MAX_PERSONS = 200

clock: Callable = utcnow  # tests move it


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


router = APIRouter(tags=["wearables"], route_class=_ErrorRoute)


def _person_ids(raw: str | None) -> list[str] | None:
    """?person_id=a,b,c (OpenAPI style form, explode false): at most 200 UUIDs, or 422."""
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",") if p.strip()]
    if len(parts) > MAX_PERSONS:
        raise HTTPException(422, f"at most {MAX_PERSONS} person_id values")
    try:
        return sorted({str(UUID(p)) for p in parts})
    except ValueError:
        raise HTTPException(422, "person_id must be a comma-separated list of UUIDs") from None


@router.get("/alerts")
def list_alerts(
    person_id: Annotated[str | None, Query(max_length=8000)] = None,
    kind: Annotated[
        str | None, Query(pattern="^(link_expired|link_revoked|sync_failing|no_recent_data|not_linked)$")
    ] = None,
    cursor: Annotated[str | None, Query(max_length=300)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    db: Session = Depends(get_db),
    p: Principal = Depends(require(READ)),
):
    persons = _person_ids(person_id)
    if cursor:
        try:
            alerts_service.decode_cursor(cursor)
        except alerts_service.InvalidCursorError:
            raise HTTPException(400, "invalid_cursor") from None
    everything = alerts_service.compute(db, Config.load(), clock(), persons, kind)
    items, nxt = alerts_service.page(everything, cursor, limit)
    return {"items": items, "next_cursor": nxt}
