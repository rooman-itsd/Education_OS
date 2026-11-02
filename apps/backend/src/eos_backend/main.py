from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager

from eos_core import oidc
from eos_core.db import SessionLocal, init_db
from eos_core.settings import settings
from fastapi import APIRouter, FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .gateway import EntitlementGate
from .modules import enabled, router_for
from .observability import REQUEST_ID, RequestContext, configure_logging, init_sentry

log = logging.getLogger("eos.api")

# The platform services' routers as create_app mounts them, from the YAML's `platform` list
# (tests/test_platform_permissions.py checks every route of these).
PLATFORM_ROUTERS = {e.name: f"{e.package}.api.router" for e in enabled() if e.kind == "platform"}


@asynccontextmanager
async def lifespan(app: FastAPI):
    # The Compose stack and CI's Postgres step migrate as the owner first (infra/docker/migrate.sh) and run the
    # API as eos_app, which may not change the schema; SQLite, local dev and tests create it here.
    if os.environ.get("EOS_DB_MANAGE_SCHEMA", "true").lower() == "true":
        init_db()
    from eos_billing.application.service import seed_plans
    from eos_identity.application import service as identity
    from eos_tenancy.application import service as tenancy

    # identity learns organisation status and slugs from tenancy without importing it (rule 1)
    identity.hooks.status = tenancy.organisation_status
    identity.hooks.id_for_slug = tenancy.organisation_id_for_slug
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
    routers = {e.name: router_for(e) for e in entries}
    mounted = sorted(e.name for e in entries if e.kind != "platform")
    app = FastAPI(title="Education OS API", version="0.1.0", lifespan=lifespan)
    app.add_middleware(EntitlementGate)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=[REQUEST_ID],
    )
    # Outermost: every log line of the request carries its request and organisation ids (observability.py).
    app.add_middleware(RequestContext)

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


configure_logging()
init_sentry()
app = create_app()
