"""The entitlement gate (ADR-0005). Every request to /api/v1/<module>/... for a feature module must come
from a user whose organisation is entitled to that module. Platform services are always reachable;
they do their own permission checks."""

from __future__ import annotations

import jwt
import structlog
from eos_core.db import SessionLocal
from eos_core.entitlement import PLATFORM_MODULES, module_entitled
from eos_core.security import decode_token
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

PREFIX = "/api/v1/"
PUBLIC = {"health"}


class EntitlementGate(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(PREFIX):
            return await call_next(request)
        module = path[len(PREFIX) :].split("/", 1)[0]
        if module in PLATFORM_MODULES or module in PUBLIC:
            return await call_next(request)
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse({"detail": "missing bearer token"}, status_code=401)
        try:
            claims = decode_token(auth.split(" ", 1)[1])
        except jwt.PyJWTError as e:
            return JSONResponse({"detail": f"invalid token: {e}"}, status_code=401)
        org = claims.get("org")
        request.state.organisation_id = org  # verified above; the request log line uses it (observability.py)
        # and every line the module writes: a Keycloak token is verified only here, not in RequestContext
        structlog.contextvars.bind_contextvars(organisation_id=org)
        if not org:
            return JSONResponse({"detail": "feature modules need an organisation user"}, status_code=403)
        from eos_tenancy.application import service as tenancy  # lazy: avoid import cycles at startup

        db = SessionLocal()
        try:
            ent = tenancy.entitlement(db, org)
        finally:
            db.close()
        if ent["status"] != "active":
            return JSONResponse(
                {"detail": f"organisation is {ent['status']}", "code": "organisation_inactive"}, status_code=403
            )
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
