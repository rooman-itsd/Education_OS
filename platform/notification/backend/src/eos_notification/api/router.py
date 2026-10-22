"""HTTP surface of notification, following contracts/openapi.yaml (merged 0.1.0).

Deliberately NOT here: POST /messages/{id}/resend. The contract promises it is audited and there is no audit
service yet, so the route is held until audit exists or the contract owner approves a documented change.
There is also no operator route to unstick queued or sending messages; recovery is internal (recover_stuck)."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from eos_core.db import get_db
from eos_identity.api.deps import Principal, require, require_organisation
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy.orm import Session

from ..application import messages, preferences, templates
from ..application.common import canonical_uuid
from ..domain.errors import NotificationError
from . import schemas
from .schemas import Channel, NewMessageIn, NewTemplateIn, PreferencesIn, PreviewIn, PublicStatus

router = APIRouter(tags=["notification"])


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except NotificationError as e:
        raise HTTPException(e.status, e.detail) from e


@router.post("/messages", status_code=202)
def send_message(
    body: NewMessageIn,
    response: Response,
    p: Principal = Depends(require("notification:message:send")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        message, created = messages.send_message(
            db,
            template=body.template,
            recipient=body.recipient.model_dump(),
            channel=body.channel,
            category=body.category,
            variables=body.variables,
            client_token=body.client_token,
            attachments=body.attachments,
            send_after=body.send_after,
        )
    if not created:
        response.status_code = 200  # the original, not a second send
    return schemas.message_out(message)


@router.get("/messages")
def list_messages(
    recipient_id: str | None = None,
    template: str | None = None,
    channel: Channel | None = None,
    status: PublicStatus | None = None,
    sent_from: datetime | None = None,
    sent_to: datetime | None = None,
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    p: Principal = Depends(require("notification:message:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        rows, total = messages.list_messages(
            db,
            recipient_id=recipient_id,
            template=template,
            channel=channel,
            statuses=schemas.status_filter(status),
            sent_from=sent_from,
            sent_to=sent_to,
            limit=limit,
            offset=offset,
        )
    return {"items": [schemas.message_out(m) for m in rows], "total": total}


@router.get("/messages/{message_id}")
def get_message(
    message_id: str,
    p: Principal = Depends(require("notification:message:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return schemas.message_out(messages.get_message(db, message_id))


@router.get("/templates")
def list_templates(
    channel: Channel | None = None,
    locale: str | None = None,
    p: Principal = Depends(require("notification:template:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return templates.list_templates(db, channel, locale)


@router.post("/templates", status_code=201)
def upsert_template(
    body: NewTemplateIn,
    p: Principal = Depends(require("notification:template:write")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return templates.upsert_template(
            db,
            key=body.key,
            channel=body.channel,
            locale=body.locale,
            body=body.body,
            subject=body.subject,
            category=body.category,
            variables=body.variables,
        )


@router.post("/templates/{key}/preview")
def preview_template(
    key: str,
    body: PreviewIn,
    p: Principal = Depends(require("notification:template:read")),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return templates.preview(db, key=key, variables=body.variables, channel=body.channel, locale=body.locale)


def _own_or_manage(user_id: str, p: Principal) -> str:
    """A person may always read and change their own preferences; anyone else needs preference:manage. The id is
    compared in canonical form, so an upper-case or braced spelling of one's own id is still one's own."""
    with _http_errors():
        uid = canonical_uuid(user_id, "user_id") or ""
    if uid != p.user_id and not p.can("notification:preference:manage"):
        raise HTTPException(403, "requires notification:preference:manage")
    return uid


@router.get("/preferences/{user_id}")
def get_preferences(user_id: str, p: Principal = Depends(require_organisation), db: Session = Depends(get_db)):
    uid = _own_or_manage(user_id, p)
    with _http_errors():
        return preferences.get_preferences(db, uid)


@router.put("/preferences/{user_id}")
def set_preferences(
    user_id: str,
    body: PreferencesIn,
    p: Principal = Depends(require_organisation),
    db: Session = Depends(get_db),
):
    uid = _own_or_manage(user_id, p)
    with _http_errors():
        return preferences.set_preferences(
            db,
            uid,
            channels=body.channels,
            locale=body.locale,
            quiet_hours=body.quiet_hours.model_dump() if body.quiet_hours else None,
            actor=p.user_id,
        )


@router.get("/inbox")
def list_inbox(
    unread_only: bool = False,
    limit: int = Query(20, ge=1, le=100),
    p: Principal = Depends(require_organisation),
    db: Session = Depends(get_db),
):
    with _http_errors():
        rows, unread = messages.list_inbox(db, p.user_id, unread_only=unread_only, limit=limit)
    return {"items": [schemas.message_out(m) for m in rows], "unread": unread}


@router.post("/inbox/{message_id}/read", status_code=204)
def mark_read(message_id: str, p: Principal = Depends(require_organisation), db: Session = Depends(get_db)):
    with _http_errors():
        messages.mark_read(db, p.user_id, message_id)
    return Response(status_code=204)
