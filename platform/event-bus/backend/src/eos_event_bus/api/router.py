"""HTTP surface of event-bus, following contracts/openapi.yaml: an operator view of the outbox. Modules never
publish through it; they call eos_core.events.publish() inside their own transaction."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
from typing import Literal

from eos_core.db import get_db
from eos_core.tenant import platform_scope
from eos_identity.api.deps import Principal, require
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..application import events
from ..infrastructure.config import EventBusConfig

router = APIRouter(tags=["event-bus"])

ADMIN = "platform:event-bus:admin"


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except events.EventBusError as e:
        raise HTTPException(e.status, e.detail) from e


@contextmanager
def _scope(p: Principal, organisation_id: str | None = None) -> Iterator[events.Scope]:
    """The super admin reads in platform scope (every organisation, or one); anyone else only their own."""
    if p.super_admin and p.can(ADMIN):
        with platform_scope():
            yield events.Scope(organisation_id, every_organisation=True)
        return
    if not p.organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    yield events.Scope(p.organisation_id)


@router.get("/events")
def list_events(
    name: str | None = Query(None, max_length=121),
    state: Literal["pending", "published", "dead_lettered"] | None = None,
    organisation_id: str | None = None,
    occurred_from: datetime | None = None,
    occurred_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("event-bus:event:read")),
    db: Session = Depends(get_db),
):
    config = EventBusConfig.from_env()
    with _scope(p, organisation_id) as scope:
        rows, total = events.list_events(
            db,
            scope,
            config,
            name=name,
            state=state,
            occurred_from=occurred_from,
            occurred_to=occurred_to,
            limit=limit,
            offset=offset,
        )
        return {"items": [events.event_out(r, config) for r in rows], "total": total}


@router.get("/events/{event_id}")
def get_event(event_id: str, p: Principal = Depends(require("event-bus:event:read")), db: Session = Depends(get_db)):
    config = EventBusConfig.from_env()
    with _scope(p) as scope, _http_errors():
        return events.event_out(events.get_event(db, scope, event_id), config)


@router.post("/events/{event_id}/replay", status_code=202)
def replay_event(
    event_id: str, p: Principal = Depends(require("event-bus:event:replay")), db: Session = Depends(get_db)
):
    config = EventBusConfig.from_env()
    with _scope(p) as scope, _http_errors():
        return events.event_out(events.replay(db, scope, config, event_id, actor=p.user_id), config)


@router.get("/relay/health")
def relay_health(p: Principal = Depends(require("event-bus:relay:read")), db: Session = Depends(get_db)):
    """Backlog across every organisation, so platform-level: only the super admin holds the key."""
    config = EventBusConfig.from_env()
    with platform_scope():
        return events.health(db, config, transport=config.transport)
