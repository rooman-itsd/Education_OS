"""HTTP surface of integration-hub, following contracts/openapi.yaml (0.2.0). Mounted by apps/backend at
/api/v1/integration-hub. Every route names its catalogue key through eos_identity's require(); the provider-facing
routes (/oauth/callback, /inbound) are public by necessity and verified by state or by the adapter.

Errors are the contract's Error body, {code, detail}. Modules never call this API to use a port: they call
`invoke` in process (application/invoke.py)."""

from __future__ import annotations

import functools
from datetime import datetime

import jwt
from eos_core.db import get_db
from eos_core.security import decode_token
from eos_identity.api.deps import Principal, current_principal, require
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query, Request, Response, status
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, RedirectResponse
from sqlalchemy.orm import Session

from ..application import access, authorisation, catalogue, connections, deliveries, inbound
from ..application.common import Actor, aware
from ..domain.errors import HubError
from ..domain.vocabulary import CREDENTIAL_NAME_RE, DELIVERY_STATUSES, NAME_RE
from ..infrastructure.config import HubConfig
from . import schemas
from .schemas import PortId

router = APIRouter(tags=["integration-hub"])

Id = str
LinkStatus = str


def _errors(fn):
    """Render a HubError as the contract's Error body with its status."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HubError as e:
            kwargs_db = kwargs.get("db")
            if kwargs_db is not None:
                kwargs_db.rollback()
            return JSONResponse(e.body(), status_code=e.status)

    return wrapper


def _actor(p: Principal) -> Actor:
    return Actor(user_id=p.user_id, organisation_id=p.organisation_id, permissions=set(p.permissions))


def _org(permission: str):
    return require(permission, organisation=True)


def _mode_guard(p: Principal = Depends(current_principal)) -> Principal:
    """POST /connections/{id}/mode needs go-live to go live and manage otherwise; the body decides which, so the
    handler checks the exact key and this guard only refuses a caller who holds neither."""
    if not (p.can(access.CONNECTION_MANAGE) or p.can(access.CONNECTION_GO_LIVE)):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {access.CONNECTION_MANAGE}")
    if not p.organisation_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "this endpoint needs an organisation user")
    return p


_mode_guard.permission = access.CONNECTION_MANAGE  # type: ignore[attr-defined]  # read by the route-coverage test


def _items(items: list) -> dict:
    return {"items": items}


def _bind_browser(response: Response, binding: authorisation.BrowserBinding) -> None:
    """The cookie that ties a pending authorisation to this browser (application/authorisation.py)."""
    response.set_cookie(
        binding.name,
        binding.value,
        max_age=binding.max_age,
        path=binding.path,
        secure=True,
        httponly=True,
        samesite="lax",
    )


# ------------------------------------------------------------------ ports and adapters


@router.get("/ports")
def list_ports(_p: Principal = Depends(require(access.ADAPTER_READ))):
    return _items(catalogue.list_ports())


@router.get("/adapters")
def list_adapters(port: PortId | None = None, _p: Principal = Depends(require(access.ADAPTER_READ))):
    return _items(catalogue.list_adapters(port))


# ------------------------------------------------------------------ connections


@router.get("/connections")
@_errors
def list_connections(
    port: PortId | None = None,
    adapter: str | None = Query(default=None, max_length=64),
    enabled: bool | None = None,
    _p: Principal = Depends(_org(access.CONNECTION_READ)),
    db: Session = Depends(get_db),
):
    return _items(connections.list_connections(db, port=port, adapter=adapter, enabled=enabled))


@router.post("/connections", status_code=201)
@_errors
def create_connection(
    body: schemas.ConnectionIn, p: Principal = Depends(_org(access.CONNECTION_MANAGE)), db: Session = Depends(get_db)
):
    if not NAME_RE.match(body.adapter):
        raise HubError(409, "adapter_not_installed", "adapter is not installed")
    if not NAME_RE.match(body.provider):
        raise HubError(409, "provider_not_offered", "provider is not offered")
    return connections.create_connection(db, _actor(p), body.model_dump())


@router.get("/connections/{id}")
@_errors
def get_connection(id: Id, _p: Principal = Depends(_org(access.CONNECTION_READ)), db: Session = Depends(get_db)):
    return connections.get(db, id)


@router.patch("/connections/{id}")
@_errors
def update_connection(
    id: Id,
    body: schemas.ConnectionUpdateIn,
    p: Principal = Depends(_org(access.CONNECTION_MANAGE)),
    db: Session = Depends(get_db),
):
    return connections.update_connection(db, _actor(p), id, body.model_dump(exclude_unset=True))


@router.get("/connections/{id}/credentials")
@_errors
def list_credentials(id: Id, _p: Principal = Depends(_org(access.CONNECTION_READ)), db: Session = Depends(get_db)):
    return _items(connections.list_credentials(db, id))


def _credential_name(name: str) -> str:
    if not CREDENTIAL_NAME_RE.match(name):
        raise HubError(422, "unknown_credential", "not a credential name")
    return name


@router.put("/connections/{id}/credentials/{name}")
@_errors
def set_credential(
    id: Id,
    name: str,
    body: schemas.CredentialIn,
    p: Principal = Depends(_org(access.CONNECTION_MANAGE)),
    db: Session = Depends(get_db),
):
    return connections.set_credential(db, _actor(p), id, _credential_name(name), body.value, aware(body.expires_at))


@router.delete("/connections/{id}/credentials/{name}", status_code=204)
@_errors
def delete_credential(
    id: Id,
    name: str,
    p: Principal = Depends(_org(access.CONNECTION_MANAGE)),
    db: Session = Depends(get_db),
):
    if not CREDENTIAL_NAME_RE.match(name):
        raise HubError(404, "not_found", "credential not found in your organisation")
    connections.delete_credential(db, _actor(p), id, name)
    return Response(status_code=204)


@router.post("/connections/{id}/authorise")
@_errors
def authorise_connection(
    id: Id,
    response: Response,
    body: schemas.AuthoriseIn | None = None,
    p: Principal = Depends(_org(access.CONNECTION_MANAGE)),
    db: Session = Depends(get_db),
):
    out, binding = authorisation.authorise_connection(db, _actor(p), id, body.return_url if body else None)
    _bind_browser(response, binding)
    return out


@router.post("/connections/{id}/mode")
@_errors
def set_mode(id: Id, body: schemas.ModeIn, p: Principal = Depends(_mode_guard), db: Session = Depends(get_db)):
    needed = access.CONNECTION_GO_LIVE if body.mode == "live" else access.CONNECTION_MANAGE
    if not p.can(needed):
        raise HTTPException(status.HTTP_403_FORBIDDEN, f"requires {needed}")
    return connections.set_mode(db, _actor(p), id, body.mode, body.confirm_live)


@router.post("/connections/{id}/enable")
@_errors
def enable(id: Id, p: Principal = Depends(_org(access.CONNECTION_MANAGE)), db: Session = Depends(get_db)):
    return connections.enable(db, _actor(p), id)


@router.post("/connections/{id}/disable")
@_errors
def disable(
    id: Id,
    body: schemas.DisableIn | None = None,
    p: Principal = Depends(_org(access.CONNECTION_MANAGE)),
    db: Session = Depends(get_db),
):
    return connections.disable(db, _actor(p), id, body.reason if body else None)


@router.get("/connections/{id}/health")
@_errors
def get_health(id: Id, _p: Principal = Depends(_org(access.CONNECTION_READ)), db: Session = Depends(get_db)):
    return connections.get_health(db, id)


@router.post("/connections/{id}/health")
@_errors
def run_health(id: Id, _p: Principal = Depends(_org(access.CONNECTION_READ)), db: Session = Depends(get_db)):
    return connections.run_health(db, id)


# ------------------------------------------------------------------ OAuth callback (public)


def _caller_of(authorization: str | None) -> str | None:
    """The person a callback is authenticated as: None without a token, "" when the token does not verify."""
    if not authorization:
        return None
    if not authorization.lower().startswith("bearer "):
        return ""
    try:
        sub = decode_token(authorization.split(" ", 1)[1]).get("sub")
    except jwt.PyJWTError:
        return ""
    return sub if isinstance(sub, str) else ""


@router.get("/oauth/callback/{adapter}", status_code=302, response_class=RedirectResponse)
@_errors
def oauth_callback(
    adapter: str,
    request: Request,
    state: str = Query(max_length=512),
    code: str | None = Query(default=None, max_length=4096),
    error: str | None = Query(default=None, max_length=512),
    authorization: str | None = Header(default=None),
    db: Session = Depends(get_db),
):
    if not NAME_RE.match(adapter):
        raise HubError(401, "state_invalid", "unknown or expired state")
    cookie = authorisation.binding_cookie_name(state)
    url = authorisation.callback(
        db,
        adapter,
        code,
        state,
        error,
        binding=request.cookies.get(cookie),
        caller_id=_caller_of(authorization),
    )
    response = RedirectResponse(url, status_code=302)
    response.delete_cookie(cookie, path=authorisation.binding_cookie_path(), secure=True, httponly=True, samesite="lax")
    return response


# ------------------------------------------------------------------ account links


@router.get("/me/account-links")
@_errors
def my_account_links(p: Principal = Depends(_org(access.SELF_LINK)), db: Session = Depends(get_db)):
    return _items(authorisation.my_links(db, _actor(p)))


@router.post("/me/account-links", status_code=201)
@_errors
def create_my_account_link(
    body: schemas.AccountLinkIn,
    response: Response,
    p: Principal = Depends(_org(access.SELF_LINK)),
    db: Session = Depends(get_db),
):
    if not NAME_RE.match(body.provider):
        raise HubError(409, "provider_not_offered", "provider is not offered")
    out, binding = authorisation.start_link(db, _actor(p), body.model_dump())
    _bind_browser(response, binding)
    return out


@router.delete("/me/account-links/{id}", status_code=204)
@_errors
def delete_my_account_link(id: Id, p: Principal = Depends(_org(access.SELF_LINK)), db: Session = Depends(get_db)):
    authorisation.delete_my_link(db, _actor(p), id)
    return Response(status_code=204)


@router.get("/account-links")
@_errors
def list_account_links(
    port: PortId | None = None,
    provider: str | None = Query(default=None, max_length=64),
    status_: LinkStatus | None = Query(default=None, alias="status", max_length=10),
    person_id: str | None = Query(default=None, max_length=36),
    cursor: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    _p: Principal = Depends(_org(access.ACCOUNT_LINK_READ)),
    db: Session = Depends(get_db),
):
    return authorisation.list_links(
        db, port=port, provider=provider, status=status_, person_id=person_id, cursor=cursor, limit=limit
    )


@router.post("/account-links/{id}/revoke")
@_errors
def revoke_account_link(
    id: Id,
    body: schemas.RevokeIn,
    p: Principal = Depends(_org(access.ACCOUNT_LINK_REVOKE)),
    db: Session = Depends(get_db),
):
    return authorisation.revoke_link(db, _actor(p), id, body.reason.strip())


# ------------------------------------------------------------------ provider callbacks (public)


async def _read_body(request: Request, limit: int) -> bytes | None:
    """The raw body, or None when it is over the limit (checked before and while reading, never after)."""
    declared = request.headers.get("content-length", "")
    if declared.isdigit() and int(declared) > limit:
        return None
    chunks, size = [], 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _query(request: Request) -> dict[str, str]:
    out: dict[str, str] = {}
    for k, v in list(request.query_params.multi_items())[:50]:
        if len(k) <= 100 and len(v) <= 2048 and k not in out:
            out[k] = v
    return out


def _too_large() -> JSONResponse:
    return JSONResponse({"code": "payload_too_large", "detail": "the body is too large"}, status_code=413)


async def _inbound(
    request: Request,
    background: BackgroundTasks,
    db: Session,
    adapter: str,
    connection_key: str | None = None,
    channel: str | None = None,
) -> Response:
    if not NAME_RE.match(adapter):
        return JSONResponse({"code": "not_found", "detail": "unknown callback address"}, status_code=404)
    raw = await _read_body(request, HubConfig.from_env().inbound_max_bytes)
    if raw is None:
        return _too_large()
    answer = await run_in_threadpool(
        inbound.receive,
        db,
        adapter=adapter,
        connection_key=connection_key,
        channel=channel,
        method=request.method,
        query=_query(request),
        headers=dict(request.headers),
        raw_body=raw,
        client_ip=request.client.host if request.client else None,
    )
    if answer.process_delivery_id:
        background.add_task(inbound.process_now, answer.process_delivery_id)
    if answer.status == 204:
        return Response(status_code=204, headers=answer.headers)
    return Response(
        content=answer.body, status_code=answer.status, media_type=answer.content_type, headers=answer.headers
    )


@router.post("/inbound/{adapter}")
async def receive_app_inbound(
    adapter: str, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)
) -> Response:
    return await _inbound(request, background, db, adapter)


@router.get("/inbound/{adapter}")
async def handshake_app_inbound(
    adapter: str, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)
) -> Response:
    return await _inbound(request, background, db, adapter)


@router.post("/inbound/{adapter}/{connection_key}")
async def receive_connection_inbound(
    adapter: str, connection_key: str, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)
) -> Response:
    return await _inbound(request, background, db, adapter, connection_key)


@router.get("/inbound/{adapter}/{connection_key}")
async def handshake_connection_inbound(
    adapter: str, connection_key: str, request: Request, background: BackgroundTasks, db: Session = Depends(get_db)
) -> Response:
    return await _inbound(request, background, db, adapter, connection_key)


@router.post("/inbound/{adapter}/{connection_key}/{channel}")
async def receive_provider_request(
    adapter: str,
    connection_key: str,
    channel: str,
    request: Request,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
) -> Response:
    return await _inbound(request, background, db, adapter, connection_key, channel)


# ------------------------------------------------------------------ delivery log


@router.get("/deliveries")
@_errors
def list_deliveries(
    connection_id: str | None = Query(default=None, max_length=36),
    port: PortId | None = None,
    direction: str | None = Query(default=None, pattern="^(outbound|inbound)$"),
    status_: str | None = Query(default=None, alias="status", max_length=300),
    caller_module: str | None = Query(default=None, max_length=64),
    caller_reference: str | None = Query(default=None, max_length=200),
    since: datetime | None = None,
    cursor: str | None = Query(default=None, max_length=20),
    limit: int = Query(default=50, ge=1, le=200),
    _p: Principal = Depends(_org(access.DELIVERY_READ)),
    db: Session = Depends(get_db),
):
    statuses = [s for s in (status_ or "").split(",") if s]
    if any(s not in DELIVERY_STATUSES for s in statuses):
        raise HubError(422, "invalid_status", "status must be delivery statuses, comma separated")
    filters = {
        "connection_id": connection_id,
        "port": port,
        "direction": direction,
        "status": statuses,
        "caller_module": caller_module,
        "caller_reference": caller_reference,
        "since": aware(since),
    }
    return deliveries.list_deliveries(db, filters, cursor, limit)


@router.get("/deliveries/{id}")
@_errors
def get_delivery(id: Id, _p: Principal = Depends(_org(access.DELIVERY_READ)), db: Session = Depends(get_db)):
    return deliveries.get_delivery(db, id)


@router.post("/deliveries/{id}/retry", status_code=202)
@_errors
def retry_delivery(id: Id, p: Principal = Depends(_org(access.DELIVERY_RETRY)), db: Session = Depends(get_db)):
    return deliveries.retry(db, _actor(p), id)


# ------------------------------------------------------------------ super admin


@router.get("/platform/overview")
def platform_overview(_p: Principal = Depends(require(access.PLATFORM_ADMIN)), db: Session = Depends(get_db)):
    return catalogue.overview(db)
