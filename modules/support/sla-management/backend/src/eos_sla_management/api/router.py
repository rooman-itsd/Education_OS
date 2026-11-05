"""HTTP surface of sla-management, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/sla-management (apps/backend/config/modules.enabled.yaml). Handlers only map HTTP to the use cases in
application/service.py; each declares the permission the contract names for it. Error bodies are
{code, message[, field]} inside FastAPI's `detail`."""

from __future__ import annotations

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import SlaManagementError
from ..domain.clocks import KINDS, STATES
from ..domain.policies import PRIORITIES
from ..infrastructure.config import BREACH_LIST_RANGE
from . import schemas as s
from .deps import no_nul, require

router = APIRouter(tags=["sla-management"], dependencies=[Depends(no_nul)])

LIMIT = Query(20, ge=1, le=100)
READ = require(perm.CLOCK_READ)
READ_SETUP = require(perm.CLOCK_READ, perm.POLICY_MANAGE)
MANAGE = require(perm.POLICY_MANAGE)


def _run(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except SlaManagementError as e:
        raise HTTPException(e.status, e.body()) from e


def _refuse(field: str, message: str) -> HTTPException:
    return HTTPException(422, {"code": f"invalid_{field}", "message": message, "field": field})


def _listed(value: str | None, allowed: tuple[str, ...], field: str) -> list[str] | None:
    """`state` is an array in form style without explode: state=running,paused."""
    if not value:
        return None
    values = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in values if v not in allowed]
    if unknown or not values:
        raise _refuse(field, f"unknown {field} {', '.join(unknown)[:200]}")
    return list(dict.fromkeys(values))


def _single(value: str | None, allowed: tuple[str, ...], field: str) -> str | None:
    """`kind`, `priority` and `scope` are one value each, not lists: kind=response,resolution is a 422, never a
    partial result."""
    if not value:
        return None
    if value not in allowed:
        raise _refuse(field, f"unknown {field} {value[:200]}")
    return value


def _assignee(value: str | None) -> str | None:
    """A person id, or me."""
    if not value or value == "me":
        return value or None
    if not s.UUID_RE.match(value):
        raise _refuse("assignee", "assignee must be a person id or me")
    return value.lower()


# ---------------------------------------------------------------- calendars


@router.get("/calendars")
def list_calendars(active: bool | None = None, a: Actor = Depends(READ_SETUP), db: Session = Depends(get_db)):
    return _run(svc.list_calendars, db, a, active=active)


@router.post("/calendars", status_code=201)
def create_calendar(body: s.CalendarInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_calendar, db, a, s.as_dict(body, partial=False))


@router.get("/calendars/{calendar_id}")
def get_calendar(
    calendar_id: str = Path(pattern=s.UUID_PATTERN), a: Actor = Depends(READ_SETUP), db: Session = Depends(get_db)
):
    return _run(svc.get_calendar, db, a, calendar_id.lower())


@router.patch("/calendars/{calendar_id}")
def update_calendar(
    body: s.CalendarUpdateInput,
    calendar_id: str = Path(pattern=s.UUID_PATTERN),
    a: Actor = Depends(MANAGE),
    db: Session = Depends(get_db),
):
    return _run(svc.update_calendar, db, a, calendar_id.lower(), s.as_dict(body, partial=True))


# ---------------------------------------------------------------- policies


@router.get("/policies")
def list_policies(
    priority: str | None = None,
    category_id: str | None = Query(None, pattern=s.UUID_PATTERN),
    active: bool | None = None,
    a: Actor = Depends(READ_SETUP),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_policies,
        db,
        a,
        priority=_single(priority, PRIORITIES, "priority"),
        category_id=category_id.lower() if category_id else None,
        active=active,
    )


@router.post("/policies", status_code=201)
def create_policy(body: s.PolicyInput, a: Actor = Depends(MANAGE), db: Session = Depends(get_db)):
    return _run(svc.create_policy, db, a, s.as_dict(body, partial=False))


@router.get("/policies/{policy_id}")
def get_policy(
    policy_id: str = Path(pattern=s.UUID_PATTERN), a: Actor = Depends(READ_SETUP), db: Session = Depends(get_db)
):
    return _run(svc.get_policy, db, a, policy_id.lower())


@router.patch("/policies/{policy_id}")
def update_policy(
    body: s.PolicyUpdateInput,
    policy_id: str = Path(pattern=s.UUID_PATTERN),
    a: Actor = Depends(MANAGE),
    db: Session = Depends(get_db),
):
    return _run(svc.update_policy, db, a, policy_id.lower(), s.as_dict(body, partial=True))


# ---------------------------------------------------------------- clocks and tickets


@router.get("/clocks")
def list_clocks(
    state: str | None = Query(None, max_length=200),
    kind: str | None = None,
    breached: bool | None = None,
    at_risk: bool | None = None,
    priority: str | None = None,
    category_id: str | None = Query(None, pattern=s.UUID_PATTERN),
    assignee: str | None = Query(None, max_length=36),
    ticket_number: str | None = Query(None, max_length=40),
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    return _run(
        svc.list_clocks,
        db,
        a,
        states=_listed(state, STATES, "state"),
        kind=_single(kind, KINDS, "kind"),
        breached=breached,
        at_risk=at_risk,
        priority=_single(priority, PRIORITIES, "priority"),
        category_id=category_id.lower() if category_id else None,
        assignee=_assignee(assignee),
        ticket_number=ticket_number,
        cursor=cursor,
        limit=limit,
    )


@router.get("/clocks/{clock_id}")
def get_clock(clock_id: str = Path(pattern=s.UUID_PATTERN), a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.get_clock, db, a, clock_id.lower())


@router.get("/tickets/{ticket_id}")
def ticket_sla(ticket_id: str = Path(pattern=s.UUID_PATTERN), a: Actor = Depends(READ), db: Session = Depends(get_db)):
    return _run(svc.ticket_sla, db, a, ticket_id.lower())


# ---------------------------------------------------------------- statistics


@router.get("/stats/breaches")
def breaches(
    scope: str | None = None,
    limit: int | None = Query(None, ge=BREACH_LIST_RANGE[0], le=BREACH_LIST_RANGE[1]),
    a: Actor = Depends(READ),
    db: Session = Depends(get_db),
):
    return _run(svc.breach_stats, db, a, scope=_single(scope, svc.SCOPES, "scope"), limit=limit)
