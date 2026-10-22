"""HTTP surface of helpdesk, as described in contracts/openapi.yaml. The host app mounts `router` under
/api/v1/helpdesk. Handlers only map HTTP to the use cases in application/service.py; each declares the permission
the contract names for it (the use case checks the conditional ones, such as PATCH and /assign). Error bodies are
{code, message[, field]} inside FastAPI's `detail`."""

from __future__ import annotations

from datetime import date
from typing import Literal

from eos_core.db import get_db
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import access as perm
from ..application import service as svc
from ..application.access import Actor
from ..application.errors import HelpdeskError
from ..domain.tickets import TICKET_STATUSES
from . import schemas as s
from .deps import require

router = APIRouter(tags=["helpdesk"])

LIMIT = Query(20, ge=1, le=100)


def _run(fn, *args):
    try:
        return fn(*args)
    except HelpdeskError as e:
        raise HTTPException(e.status, e.body()) from e


def _statuses(value: str | None) -> list[str] | None:
    """`status` is an array in form style without explode: status=new,on_hold."""
    if not value:
        return None
    statuses = [v.strip() for v in value.split(",") if v.strip()]
    unknown = [v for v in statuses if v not in TICKET_STATUSES]
    if unknown:
        message = f"unknown status {', '.join(unknown)}"
        raise HTTPException(422, {"code": "invalid_status", "message": message, "field": "status"})
    return statuses


# ---------------------------------------------------------------- queues and categories


@router.get("/queues")
def list_queues(
    active: bool | None = None,
    a: Actor = Depends(require(perm.TICKET_READ, perm.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_queues, db, a, active)


@router.post("/queues", status_code=201)
def create_queue(body: s.QueueInput, a: Actor = Depends(require(perm.SETTINGS_MANAGE)), db: Session = Depends(get_db)):
    return _run(svc.create_queue, db, a, s.full(body))


@router.patch("/queues/{queue_id}")
def update_queue(
    queue_id: str, body: s.QueueInput, a: Actor = Depends(require(perm.SETTINGS_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.update_queue, db, a, queue_id, s.sent(body))


@router.get("/categories")
def list_categories(
    active: bool | None = None,
    a: Actor = Depends(require(perm.SELF_RAISE, perm.TICKET_READ, perm.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_categories, db, a, active)


@router.post("/categories", status_code=201)
def create_category(
    body: s.CategoryInput, a: Actor = Depends(require(perm.SETTINGS_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.create_category, db, a, s.full(body))


@router.patch("/categories/{category_id}")
def update_category(
    category_id: str,
    body: s.CategoryInput,
    a: Actor = Depends(require(perm.SETTINGS_MANAGE)),
    db: Session = Depends(get_db),
):
    return _run(svc.update_category, db, a, category_id, s.sent(body))


# ---------------------------------------------------------------- tickets


@router.get("/tickets")
def list_tickets(
    status: str | None = None,
    priority: s.Priority | None = None,
    queue_id: str | None = None,
    category_id: str | None = None,
    assignee: str | None = None,
    requester_id: str | None = None,
    q: str | None = None,
    created_from: date | None = None,
    created_to: date | None = None,
    sort: Literal["newest", "oldest", "priority"] = "newest",
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(require(perm.TICKET_READ)),
    db: Session = Depends(get_db),
):
    filters = {
        "statuses": _statuses(status),
        "priority": priority,
        "queue_id": queue_id,
        "category_id": category_id,
        "assignee": assignee,
        "requester_id": requester_id,
        "q": q,
        "created_from": created_from,
        "created_to": created_to,
        "sort": sort,
    }
    return _run(svc.list_tickets, db, a, filters, cursor, limit)


@router.post("/tickets", status_code=201)
def raise_ticket(
    body: s.AgentTicketInput, a: Actor = Depends(require(perm.TICKET_WORK)), db: Session = Depends(get_db)
):
    return _run(svc.raise_ticket, db, a, s.full(body))


@router.get("/tickets/{ticket_id}")
def get_ticket(ticket_id: str, a: Actor = Depends(require(perm.TICKET_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_ticket, db, a, ticket_id)


@router.patch("/tickets/{ticket_id}")
def update_ticket(
    ticket_id: str,
    body: s.TicketUpdate,
    a: Actor = Depends(require(perm.TICKET_WORK, perm.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    # title, category_id and priority are not nullable in the contract: a null means "no change".
    changes = {k: v for k, v in s.sent(body).items() if v is not None or k == "reason"}
    return _run(svc.update_ticket, db, a, ticket_id, changes)


@router.post("/tickets/{ticket_id}/assign")
def assign_ticket(
    ticket_id: str,
    body: s.AssignInput,
    a: Actor = Depends(require(perm.TICKET_WORK, perm.TICKET_MANAGE)),
    db: Session = Depends(get_db),
):
    sent = s.sent(body)
    if sent.get("queue_id") is None:
        sent.pop("queue_id", None)  # "Omit to stay in the current queue"
    return _run(svc.assign_ticket, db, a, ticket_id, sent)


@router.post("/tickets/{ticket_id}/comments", status_code=201)
def add_comment(
    ticket_id: str,
    body: s.AgentCommentInput,
    a: Actor = Depends(require(perm.TICKET_WORK)),
    db: Session = Depends(get_db),
):
    return _run(svc.add_comment, db, a, ticket_id, s.full(body))


@router.post("/tickets/{ticket_id}/status")
def change_status(
    ticket_id: str, body: s.StatusInput, a: Actor = Depends(require(perm.TICKET_WORK)), db: Session = Depends(get_db)
):
    return _run(svc.change_status, db, a, ticket_id, s.full(body))


@router.post("/tickets/{ticket_id}/resolve")
def resolve_ticket(
    ticket_id: str, body: s.ResolveInput, a: Actor = Depends(require(perm.TICKET_WORK)), db: Session = Depends(get_db)
):
    return _run(svc.resolve_ticket, db, a, ticket_id, s.full(body))


@router.post("/tickets/{ticket_id}/cancel")
def cancel_ticket(
    ticket_id: str, body: s.CancelInput, a: Actor = Depends(require(perm.TICKET_MANAGE)), db: Session = Depends(get_db)
):
    return _run(svc.cancel_ticket, db, a, ticket_id, s.full(body))


@router.post("/tickets/{ticket_id}/links", status_code=201)
def add_link(
    ticket_id: str, body: s.LinkInput, a: Actor = Depends(require(perm.TICKET_WORK)), db: Session = Depends(get_db)
):
    return _run(svc.add_link, db, a, ticket_id, s.full(body))


@router.delete("/tickets/{ticket_id}/links/{link_id}", status_code=204)
def remove_link(
    ticket_id: str, link_id: str, a: Actor = Depends(require(perm.TICKET_WORK)), db: Session = Depends(get_db)
):
    _run(svc.remove_link, db, a, ticket_id, link_id)
    return Response(status_code=204)


# ---------------------------------------------------------------- the Support Staff widget


@router.get("/stats/open-by-priority")
def open_by_priority(
    scope: Literal["mine", "my_queues", "all"] | None = None,
    queue_id: str | None = None,
    a: Actor = Depends(require(perm.TICKET_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.open_by_priority, db, a, scope, queue_id)


# ---------------------------------------------------------------- the caller's own tickets


@router.get("/me/tickets")
def list_my_tickets(
    status: str | None = None,
    cursor: str | None = None,
    limit: int = LIMIT,
    a: Actor = Depends(require(perm.SELF_READ)),
    db: Session = Depends(get_db),
):
    return _run(svc.list_my_tickets, db, a, _statuses(status), cursor, limit)


@router.post("/me/tickets", status_code=201)
def raise_my_ticket(body: s.TicketInput, a: Actor = Depends(require(perm.SELF_RAISE)), db: Session = Depends(get_db)):
    return _run(svc.raise_my_ticket, db, a, s.full(body))


@router.get("/me/tickets/{ticket_id}")
def get_my_ticket(ticket_id: str, a: Actor = Depends(require(perm.SELF_READ)), db: Session = Depends(get_db)):
    return _run(svc.get_my_ticket, db, a, ticket_id)


@router.post("/me/tickets/{ticket_id}/comments", status_code=201)
def reply_to_my_ticket(
    ticket_id: str, body: s.CommentInput, a: Actor = Depends(require(perm.SELF_RAISE)), db: Session = Depends(get_db)
):
    return _run(svc.reply_to_my_ticket, db, a, ticket_id, s.full(body))


@router.post("/me/tickets/{ticket_id}/confirm")
def confirm_my_ticket(
    ticket_id: str,
    body: s.ConfirmInput | None = None,
    a: Actor = Depends(require(perm.SELF_RAISE)),
    db: Session = Depends(get_db),
):
    return _run(svc.confirm_my_ticket, db, a, ticket_id, s.full(body) if body else {})


@router.post("/me/tickets/{ticket_id}/reopen")
def reopen_my_ticket(
    ticket_id: str, body: s.Reason, a: Actor = Depends(require(perm.SELF_RAISE)), db: Session = Depends(get_db)
):
    return _run(svc.reopen_my_ticket, db, a, ticket_id, s.full(body))


@router.post("/me/tickets/{ticket_id}/withdraw")
def withdraw_my_ticket(
    ticket_id: str, body: s.Reason, a: Actor = Depends(require(perm.SELF_RAISE)), db: Session = Depends(get_db)
):
    return _run(svc.withdraw_my_ticket, db, a, ticket_id, s.full(body))
