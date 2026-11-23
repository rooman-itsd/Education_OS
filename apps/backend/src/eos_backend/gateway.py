"""The entitlement gate (ADR-0005). Every request to /api/v1/<module>/... for a feature module must come
from a user whose organisation is entitled to that module. Platform services do their own permission checks,
but a token of an organisation that is no longer active (suspended or archived) is refused on them too, on the
next request: sign-in already refuses such an organisation, and a token issued before the suspension must not
keep working for the rest of its life (security review N2).

These lookups ran on every request and were the largest single cost in the 20 Nov profile (about a fifth of the
API's CPU, tests/performance/README.md). EOS_GATE_CACHE_SECONDS lets the gate reuse an answer for that many seconds,
per API process, so a change (a suspension, a disabled user, a plan or module change) takes effect within that time
instead of on the next request. 0, the default, keeps the next-request behaviour: nothing is reused."""

from __future__ import annotations

import os
import time

import jwt
import structlog
from eos_api_gateway import token_claims
from eos_core.db import SessionLocal
from eos_core.entitlement import PLATFORM_MODULES, module_entitled
from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

PREFIX = "/api/v1/"
PUBLIC = {"health"}
CACHE_SETTING = "EOS_GATE_CACHE_SECONDS"
MAX_CACHE_SECONDS = 300.0  # a typo must not make a suspension take hours to apply
MAX_CACHE_ENTRIES = 10_000  # one per organisation and user seen; past it the cache starts again empty

# (kind, organisation, user) -> (expires at, answer). Read and written on the event loop only, so no lock is needed.
_cache: dict[tuple[str, str, str | None], tuple[float, object]] = {}


def cache_seconds() -> float:
    """EOS_GATE_CACHE_SECONDS, from 0 (the default: every request reads the database) to 300. Read on each request,
    so a test or an operator changing it needs no restart. Anything that is not a number counts as 0."""
    try:
        value = float(os.environ.get(CACHE_SETTING, "0") or 0)
    except ValueError:
        return 0.0
    return min(max(value, 0.0), MAX_CACHE_SECONDS)


def _cached(key: tuple[str, str, str | None]) -> tuple[bool, object]:
    hit = _cache.get(key)
    if hit is not None and hit[0] > time.monotonic():
        return True, hit[1]
    return False, None


def _remember(key: tuple[str, str, str | None], answer: object, seconds: float) -> None:
    if seconds <= 0:
        return
    if len(_cache) >= MAX_CACHE_ENTRIES:
        _cache.clear()
    _cache[key] = (time.monotonic() + seconds, answer)


def clear_cache() -> None:
    """Forget every remembered answer (tests)."""
    _cache.clear()


def _inactive(status: str | None) -> JSONResponse:
    return JSONResponse(
        {"detail": f"organisation is {status or 'missing'}", "code": "organisation_inactive"}, status_code=403
    )


class EntitlementGate(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(PREFIX):
            return await call_next(request)
        module = path[len(PREFIX) :].split("/", 1)[0]
        if module in PUBLIC:
            return await call_next(request)
        if module in PLATFORM_MODULES:
            return await self._platform(request, call_next)
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse({"detail": "missing bearer token"}, status_code=401)
        try:
            # decoded once per request: the rate limiter outside this gate has usually done it already
            claims = await token_claims(request) or {}
        except jwt.PyJWTError as e:
            return JSONResponse({"detail": f"invalid token: {e}"}, status_code=401)
        org = claims.get("org")
        request.state.organisation_id = org  # verified above; the request log line uses it (observability.py)
        # and every line the module writes: a Keycloak token is verified only here, not in RequestContext
        structlog.contextvars.bind_contextvars(organisation_id=org)
        if not org:
            return JSONResponse({"detail": "feature modules need an organisation user"}, status_code=403)
        # In a worker thread, never on the event loop: a pool checkout blocks while every connection is taken, and
        # the requests holding them need the loop to finish and give them back, so a burst of dashboard requests
        # would hang the whole API until the pool timed out (30 s). A remembered answer needs neither.
        key = ("entitlement", org, claims.get("sub"))
        seconds = cache_seconds()
        found, answer = _cached(key) if seconds else (False, None)
        if not found:
            answer = await run_in_threadpool(_entitlement, org, claims.get("sub"))
            _remember(key, answer, seconds)
        ent, user_status = answer
        if ent["status"] != "active":
            return _inactive(ent["status"])
        if user_status not in (None, "active"):
            # A disabled or erased user (identity, DPDP D10) is refused on the next request, as identity's
            # current_principal refuses them on platform routes: a feature module builds its principal from the
            # token alone and would otherwise accept it until it expires.
            return JSONResponse({"detail": f"user is {user_status}", "code": "user_disabled"}, status_code=401)
        if ent.get("subscription_status") == "read_only" and request.method not in ("GET", "HEAD", "OPTIONS"):
            return JSONResponse(
                {"detail": "trial ended; the organisation is read-only until it upgrades", "code": "read_only"},
                status_code=403,
            )
        if not module_entitled(ent, module):
            return JSONResponse(
                {
                    "detail": f"module {module} is not in your plan",
                    "code": "module_not_entitled",
                    "upgradable": module in {m.split("/")[-1] for m in ent["upgradable_modules"]},
                },
                status_code=403,
            )
        return await call_next(request)

    async def _platform(self, request: Request, call_next):
        """A platform service answers for itself who may call it: no token, a bad token or a token without an
        organisation (the super admin) passes through to the route's own check, unchanged. A token of an
        organisation user (impersonated or not) is refused when that organisation is not active, with the same
        403 `organisation_inactive` a feature module gives. Nothing is exempt: sign-in is refused to such an
        organisation, so the only tokens that reach here were issued before the suspension."""
        try:
            claims = await token_claims(request) or {}
        except jwt.PyJWTError:
            return await call_next(request)  # the route's current_principal answers 401 with the reason
        org = claims.get("org")
        if org:
            # One primary-key read per request, off the event loop (see dispatch), unless EOS_GATE_CACHE_SECONDS
            # lets the answer be reused; by default it does not, and a suspension takes effect on the next request.
            key = ("status", org, None)
            seconds = cache_seconds()
            found, status = _cached(key) if seconds else (False, None)
            if not found:
                status = await run_in_threadpool(_organisation_status, org)
                _remember(key, status, seconds)
            if status != "active":
                return _inactive(status)
        return await call_next(request)


def _entitlement(org: str, user_id: str | None) -> tuple[dict, str | None]:
    """The organisation's entitlement and the token user's status, in one session. The status is None when no
    identity user carries the id (nothing to refuse on: only a token signed with the platform's key reaches
    here); identity keeps a disabled or erased user's row, with that status, so those are always found."""
    from eos_identity.application import service as identity  # lazy: avoid import cycles at startup
    from eos_tenancy.application import service as tenancy

    db = SessionLocal()
    try:
        ent = tenancy.entitlement(db, org)
        user = identity.get_user(db, user_id) if user_id else None
        return ent, getattr(user, "status", None)
    finally:
        db.close()


def _organisation_status(org: str) -> str | None:
    from eos_tenancy.application import service as tenancy  # lazy: avoid import cycles at startup

    db = SessionLocal()
    try:
        return tenancy.organisation_status(db, org)
    finally:
        db.close()
