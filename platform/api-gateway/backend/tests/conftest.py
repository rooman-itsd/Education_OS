"""The service alone: a small app with the routes the gateway treats specially, a fake clock and the in-process
store. No database."""

import os

os.environ.setdefault("EOS_JWT_SECRET", "test-secret-test-secret-test-secret-32b")

import pytest
from eos_api_gateway import GatewaySettings, RateLimit, SecurityHeaders
from eos_api_gateway.domain.bucket import Limit
from eos_api_gateway.infrastructure import MemoryStore
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.testclient import TestClient

PEER = ("203.0.113.5", 40000)


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

    @app.post("/api/v1/identity/auth/login")
    def login():
        return {"token": "x"}

    @app.post("/api/v1/tenancy/register")
    def register():
        return {"id": "org"}

    @app.get("/docs")
    def docs():
        return HTMLResponse("<html>docs</html>")

    app.add_middleware(RateLimit, settings=settings, store=store or MemoryStore(), clock=clock or FakeClock())
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
