"""The service alone: a small app with the routes the gateway treats specially, a fake clock and the in-process
store. No database."""

import json
import os

os.environ.setdefault("EOS_JWT_SECRET", "test-secret-test-secret-test-secret-32b")

import pytest
from eos_api_gateway import GatewaySettings, RateLimit, SecurityHeaders
from eos_api_gateway.domain.bucket import Limit
from eos_api_gateway.infrastructure import MemoryStore
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient

PEER = ("203.0.113.5", 40000)
HANDOFF_CSP = "default-src 'none'; script-src 'nonce-abc'; form-action 'self' https:"
HANDOFF_REFERRER = "strict-origin-when-cross-origin"


class FakeClock:
    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def make_app(settings: GatewaySettings, clock: FakeClock | None = None, store: MemoryStore | None = None) -> FastAPI:
    app = FastAPI()

    @app.get("/api/v1/health")
    def health():
        return {"status": "ok"}

    @app.get("/api/v1/things")
    def things():
        return {"things": []}

    @app.get("/api/v1/cached")
    def cached():
        return JSONResponse({"x": 1}, headers={"Cache-Control": "private, max-age=60"})

    @app.get("/api/v1/handoff")
    def handoff():
        """A page the API serves on purpose, with its own policy (like the payment adapter's bank hand-off)."""
        return HTMLResponse(
            "<form></form>", headers={"Content-Security-Policy": HANDOFF_CSP, "Referrer-Policy": HANDOFF_REFERRER}
        )

    @app.post("/api/v1/identity/auth/login")
    async def login(request: Request):
        """Like identity's: 401 for a wrong password (here: the password "wrong"), 200 otherwise, 422 for
        {"password": "malformed"}. Reads the whole body, so a test can tell the route got it intact."""
        try:
            body = json.loads(await request.body() or b"null")
        except ValueError:
            body = None
        password = body.get("password") if isinstance(body, dict) else None
        if password == "wrong":
            return JSONResponse({"detail": "invalid credentials"}, status_code=401)
        if password == "malformed":
            return JSONResponse({"detail": "invalid"}, status_code=422)
        return {"token": "x", "body_bytes": len(json.dumps(body)) if body is not None else 0}

    @app.post("/api/v1/tenancy/register")
    def register():
        return {"id": "org"}

    @app.get("/docs")
    def docs():
        return HTMLResponse("<html>docs</html>")

    app.add_middleware(
        RateLimit, settings=settings, store=store if store is not None else MemoryStore(), clock=clock or FakeClock()
    )
    app.add_middleware(SecurityHeaders, settings=settings)
    return app


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def settings() -> GatewaySettings:
    """Small limits so a test reaches them in a handful of requests."""
    return GatewaySettings(
        ip=Limit(60, 3), organisation=Limit(60, 5), auth=Limit(60, 2), trusted_proxies=("10.0.0.0/8",)
    )


@pytest.fixture
def client(settings, clock) -> TestClient:
    return TestClient(make_app(settings, clock), client=PEER)
