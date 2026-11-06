"""HTTP surface of search, following contracts/openapi.yaml (draft 0.1.0).

Every route names a catalogue key through `require`. The organisation is always the caller's, taken from the session:
`organisation_id` in a query string is a 422, and in the reindex body only a super admin may name one. An engine outage
is a 503 on every route that needs the engine."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime

from eos_core.db import get_db
from eos_core.tenant import organisation_scope
from eos_identity.api.deps import Principal, current_principal, require
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request
from sqlalchemy.orm import Session

from ..application import cursor, health, reindex, service, state
from ..application.registry import get_registry
from ..domain.declarations import MODULE_RE
from ..domain.documents import Caller
from ..domain.errors import SearchError
from ..infrastructure.config import SearchConfig
from ..infrastructure.engine import get_engine
from .schemas import ReindexIn

# q, types, filters and cursor are bounded in application/service.py and application/cursor.py, not in the route
# signatures: FastAPI's own 422 for an over-long value echoes the value back, and no error may contain the query.
router = APIRouter(tags=["search"])

READ = "search:record:read"
MANAGE = "search:index:manage"
PLATFORM_READ = "platform:search:read"
MODULE_PATTERN = MODULE_RE.pattern

# Refuse to start misconfigured (the in-memory engine outside dev mode, no cursor secret): importing this router is
# what mounting the module does, so a bad deployment fails here and not on the first request.
SearchConfig.from_env().validate()


@contextmanager
def _http_errors() -> Iterator[None]:
    try:
        yield
    except SearchError as e:
        raise HTTPException(e.status, e.detail) from e


def _caller(
    request: Request, p: Principal = Depends(require(READ, organisation=True)), db: Session = Depends(get_db)
) -> Caller:
    if "organisation_id" in request.query_params:
        raise HTTPException(422, "organisation_id is not a parameter: the organisation comes from the session")
    assert p.organisation_id is not None  # require(organisation=True)
    return Caller(
        user_id=p.user_id,
        organisation_id=p.organisation_id,
        grants=frozenset(p.permissions),
        entitled_modules=state.entitled_modules(db, p.organisation_id),
    )


def _manager(p: Principal = Depends(current_principal)) -> Principal:
    """An organisation admin (search:index:manage) or a super admin (platform:search:read) may start a rebuild."""
    if not (p.can(MANAGE) or p.can(PLATFORM_READ)):
        raise HTTPException(403, f"requires {MANAGE}")
    return p


_caller.permission = READ  # type: ignore[attr-defined]  # read by the host's route-coverage check
_manager.permission = MANAGE  # type: ignore[attr-defined]  # read by the host's route-coverage check


@router.get("/query")
def search_all(
    caller: Caller = Depends(_caller),
    q: str = Query(...),
    types: str | None = Query(None),
    cursor_token: str | None = Query(None, alias="cursor"),
    limit: int = Query(20, ge=1, le=50),
):
    with _http_errors():
        return service.search(caller, q=q, types=types, cursor_token=cursor_token, limit=limit)


@router.get("/modules/{module}/query")
def search_module(
    module: str = Path(..., pattern=MODULE_PATTERN),
    caller: Caller = Depends(_caller),
    q: str = Query(...),
    types: str | None = Query(None),
    filters: str | None = Query(None),
    cursor_token: str | None = Query(None, alias="cursor"),
    limit: int = Query(20, ge=1, le=50),
):
    with _http_errors():
        return service.search(
            caller, q=q, module=module, types=types, filters=filters, cursor_token=cursor_token, limit=limit
        )


@router.get("/suggest")
def suggest(
    caller: Caller = Depends(_caller),
    q: str = Query(...),
    types: str | None = Query(None),
    limit: int = Query(5, ge=1, le=10),
):
    with _http_errors():
        return service.suggest(caller, q=q, types=types, limit=limit)


@router.get("/types")
def list_types(caller: Caller = Depends(_caller)):
    return service.list_types(caller)


# --- reindex -----------------------------------------------------------------------------------------------------
@router.post("/reindex", status_code=202)
def start_reindex(
    body: ReindexIn,
    background: BackgroundTasks,
    p: Principal = Depends(_manager),
    db: Session = Depends(get_db),
):
    if body.organisation_id is not None and not p.can(PLATFORM_READ):
        raise HTTPException(403, f"naming an organisation requires {PLATFORM_READ}")
    organisation_id = str(body.organisation_id) if body.organisation_id is not None else p.organisation_id
    if not organisation_id:
        raise HTTPException(422, "organisation_id is required without an organisation session")
    if body.organisation_id is None and not p.can(MANAGE):
        raise HTTPException(403, f"requires {MANAGE}")
    config = SearchConfig.from_env().validate()
    with _http_errors(), organisation_scope(organisation_id):
        job = reindex.start_reindex(
            db,
            organisation_id=organisation_id,
            requested_by=p.user_id,
            module=body.module,
            type_key=body.type,
            config=config,
        )
        db.commit()
        out = reindex.job_out(job)
    if config.job_runner == "arq":
        reindex.enqueue_arq(job.id, config)
    else:
        background.add_task(reindex.run_reindex_job, job.id)
    return out


@router.get("/reindex")
def list_reindex_jobs(
    module: str | None = Query(None, pattern=MODULE_PATTERN, max_length=64),
    status: str | None = Query(None, pattern="^(queued|running|succeeded|failed|cancelled)$"),
    cursor_token: str | None = Query(None, alias="cursor"),
    limit: int = Query(20, ge=1, le=50),
    p: Principal = Depends(require(MANAGE, organisation=True)),
    db: Session = Depends(get_db),
):
    config = SearchConfig.from_env().validate()
    bound = cursor.query_hash("reindex", module, status)
    after = None
    with _http_errors():
        if cursor_token:
            payload = cursor.verify(config.cursor_secret, cursor_token, user_id=p.user_id, bound_to=bound)
            try:
                after = (datetime.fromisoformat(str(payload["t"])), str(payload["i"]))
            except (KeyError, ValueError):
                raise SearchError(422, cursor.BAD_CURSOR) from None
        rows = reindex.list_jobs(db, p.organisation_id, module=module, status=status, limit=limit, after=after)
    page = rows[:limit]
    next_cursor = None
    if len(rows) > limit:
        last = page[-1]
        next_cursor = cursor.sign(
            config.cursor_secret,
            {"u": p.user_id, "h": bound, "t": state.aware(last.requested_at).isoformat(), "i": last.id},
            ttl_seconds=config.cursor_ttl_seconds,
        )
    return {"items": [reindex.job_out(j) for j in page], "next_cursor": next_cursor}


@router.get("/reindex/{job_id}")
def get_reindex_job(
    job_id: str = Path(..., max_length=64),
    p: Principal = Depends(require(MANAGE, organisation=True)),
    db: Session = Depends(get_db),
):
    with _http_errors():
        return reindex.job_out(reindex.get_job(db, p.organisation_id, job_id))


# --- health ------------------------------------------------------------------------------------------------------
@router.get("/health")
def index_health(p: Principal = Depends(require(MANAGE, organisation=True)), db: Session = Depends(get_db)):
    entitled = state.entitled_modules(db, p.organisation_id)
    return health.index_health(db, p.organisation_id, get_engine(), entitled, get_registry())


@router.get("/platform/health")
def platform_health(p: Principal = Depends(require(PLATFORM_READ)), db: Session = Depends(get_db)):
    return health.platform_health(db, get_engine(), get_registry())
