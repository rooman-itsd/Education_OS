"""Fixtures only. Everything the tests share lives in vc_support.py, imported by a unique name rather than from
`conftest`, which in a combined run can be another module's."""

import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/video_conferencing_test.db"  # never a real database
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[3]))  # every permissions.yaml

import httpx
import pytest
from vc_support import DATA_KEY, ZOOM_SECRET, Clock, Documents, Transport


@pytest.fixture(scope="session", autouse=True)
def database():
    from eos_core.db import init_db
    from eos_video_conferencing.infrastructure import models  # noqa: F401  registers the tables

    init_db()


@pytest.fixture(autouse=True)
def clean_tables(database):
    """Every test starts from empty tables: provider ids in the fixtures are fixed, so rows must not carry over."""
    from eos_core.db import SessionLocal
    from eos_core.tenant import platform_scope
    from eos_video_conferencing.infrastructure.models import TABLES

    yield
    with platform_scope(), SessionLocal() as db:
        for t in reversed(TABLES):
            db.execute(t.delete())
        db.commit()


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    """No test may open a socket: a client built without a MockTransport fails loudly."""

    def refuse(self, request):
        raise AssertionError(f"a test tried to reach the network: {request.method} {request.url}")

    monkeypatch.setattr(httpx.HTTPTransport, "handle_request", refuse)


@pytest.fixture(autouse=True)
def env(monkeypatch):
    for k in list(os.environ):
        if k.startswith("VIDEO_CONFERENCING_"):
            monkeypatch.delenv(k)
    monkeypatch.setenv("VIDEO_CONFERENCING_ZOOM_WEBHOOK_SECRET_TOKEN", ZOOM_SECRET)
    monkeypatch.setenv("VIDEO_CONFERENCING_ZOOM_CLIENT_ID", "platform-zoom-id")
    monkeypatch.setenv("VIDEO_CONFERENCING_ZOOM_CLIENT_SECRET", "platform-zoom-secret")
    monkeypatch.setenv("VIDEO_CONFERENCING_TEAMS_CLIENT_ID", "platform-teams-id")
    monkeypatch.setenv("VIDEO_CONFERENCING_TEAMS_CLIENT_SECRET", "platform-teams-secret")
    monkeypatch.setenv("VIDEO_CONFERENCING_WEBEX_CLIENT_ID", "platform-webex-id")
    monkeypatch.setenv("VIDEO_CONFERENCING_WEBEX_CLIENT_SECRET", "platform-webex-secret")
    monkeypatch.setenv("VIDEO_CONFERENCING_DATA_KEY", DATA_KEY)
    monkeypatch.setenv("VIDEO_CONFERENCING_PUBLIC_BASE_URL", "https://educationos.example")
    from eos_video_conferencing.infrastructure import crypto, providers  # noqa: F401
    from eos_video_conferencing.infrastructure.providers import teams, zoom

    zoom._TOKENS.clear()
    teams._TOKENS.clear()
    _ = crypto


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def transport():
    t = Transport()
    yield t
    assert not t.unexpected, f"requests nothing routed: {t.unexpected}"


@pytest.fixture
def documents():
    return Documents()


@pytest.fixture
def adapter(transport, clock, documents):
    from eos_video_conferencing.application.adapter import VideoConferencingAdapter

    return VideoConferencingAdapter(client_factory=transport.factory(), clock=clock, documents=documents)


@pytest.fixture
def org():
    from vc_support import Org

    return Org()


@pytest.fixture
def other_org():
    from vc_support import Org

    return Org()


@pytest.fixture
def client():
    """The operator API alone, as module-standard rule 6 asks: no host and no other module."""
    from eos_video_conferencing.api.router import router
    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from vc_support import PREFIX

    app = FastAPI()
    app.include_router(router, prefix=PREFIX)
    with TestClient(app) as c:
        yield c
