from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from eos_api_gateway import GatewaySettings, RateLimit, SecurityHeaders
from eos_core import oidc
from eos_core.db import SessionLocal, init_db
from eos_core.settings import settings
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .gateway import EntitlementGate
from .modules import enabled, middleware_only, router_for

log = logging.getLogger("eos.api")

# The platform services' routers as create_app mounts them, from the YAML's `platform` list
# (tests/test_platform_permissions.py checks every route of these). Only a service whose module.yaml says
# `router: false` (api-gateway, middleware only) is left out; any other must have a router, or start-up fails.
PLATFORM_ROUTERS = {
    e.name: f"{e.package}.api.router" for e in enabled() if e.kind == "platform" and not middleware_only(e)
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The Compose stack and CI's Postgres step migrate as the owner first (infra/docker/migrate.sh) and run the
    # API as eos_app, which may not change the schema; SQLite, local dev and tests create it here.
    if os.environ.get("EOS_DB_MANAGE_SCHEMA", "true").lower() == "true":
        init_db()
    from eos_billing.application import service as billing
    from eos_identity.application import service as identity
    from eos_tenancy.application import service as tenancy

    seed_plans = billing.seed_plans
    # identity learns organisation status and slugs from tenancy, and the plan's user limit from billing,
    # without importing either (rule 1)
    identity.hooks.status = tenancy.organisation_status
    identity.hooks.id_for_slug = tenancy.organisation_id_for_slug
    identity.hooks.user_limit = billing.user_limit
    # eos_core verifies a Keycloak realm token (ADR-0006); identity owns the mapping to a user
    oidc.hooks.resolve_claims = identity.resolve_oidc_claims
    seed_super_admin = identity.seed_super_admin

    db = SessionLocal()
    try:
        seed_plans(db)
        seed_super_admin(db)
    finally:
        db.close()
    yield


def create_app(extra_routers: dict[str, APIRouter] | None = None) -> FastAPI:
    """Mount everything config/modules.enabled.yaml lists (platform services, feature modules, integrations),
    plus `extra_routers` (tests). Fails before serving anything if a listed entry is not installed."""
    entries = enabled()
    routers = {e.name: r for e in entries if (r := router_for(e)) is not None}
    mounted = sorted(e.name for e in entries if e.kind != "platform")
    app = FastAPI(title="Education OS API", version="0.1.0", lifespan=lifespan)
    # Middleware, innermost first (Starlette wraps each around the previous): the entitlement gate, then the
    # rate limiter (a refused request costs no database query), then CORS (so a browser may read a 429), then
    # the security headers on every response, the refusals included. platform/api-gateway/README.md has the
    # settings; they are read here, once, so tests may build an app under other values.
    gateway = GatewaySettings.from_env()
    if gateway.rate_limit and gateway.proxies_unset and not settings.dev_mode:
        log.warning(
            "EOS_TRUSTED_PROXIES is not set: X-Forwarded-For is ignored, so behind a reverse proxy every anonymous "
            "request, sign-ins included, counts against the proxy's address and one bucket. Set it to the proxy's "
            "address (platform/api-gateway/README.md)."
        )
    app.add_middleware(EntitlementGate)
    app.add_middleware(RateLimit, settings=gateway)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeaders, settings=gateway)

    @app.get("/api/v1/health")
    def health():
        return {
            "status": "ok",
            "database": "postgres" if settings.is_postgres else "sqlite",
            "dev_mode": settings.dev_mode,
            "modules": mounted,
        }

    for name, router in routers.items():
        app.include_router(router, prefix=f"/api/v1/{name}")
    for name, router in (extra_routers or {}).items():
        app.include_router(router, prefix=f"/api/v1/{name}")
    return app


app = create_app()
