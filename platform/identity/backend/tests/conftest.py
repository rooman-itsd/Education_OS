"""identity's own test app: its router alone on a throwaway SQLite file, organisations faked through the hooks
apps/backend normally fills from tenancy, and a Keycloak realm faked with a key pair generated here (ADR-0006).
The suite must pass with this module installed alone (module standard)."""

from __future__ import annotations

import os
import tempfile
from dataclasses import replace
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/identity.db")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core import oidc
from eos_core.db import SessionLocal, init_db
from eos_core.settings import settings
from eos_identity.api.router import router
from eos_identity.application import service
from fastapi import FastAPI
from fastapi.testclient import TestClient
from oidc_fake import CLIENT_ID, ISSUER_BASE, ORGS, Realm


def _id_for_slug(db, slug):  # noqa: ARG001
    return ORGS.get(slug, (None, None))[0]


def _status(db, org_id):  # noqa: ARG001
    return next((st for i, st in ORGS.values() if i == org_id), None)


@pytest.fixture(scope="session")
def client():
    init_db()
    service.hooks.id_for_slug = _id_for_slug
    service.hooks.status = _status
    oidc.hooks.resolve_claims = service.resolve_oidc_claims
    app = FastAPI()
    app.include_router(router, prefix="/api/v1/identity")
    with TestClient(app) as c:
        yield c


@pytest.fixture
def db():
    s = SessionLocal()
    try:
        yield s
    finally:
        s.close()


@pytest.fixture
def oidc_settings(monkeypatch):
    """OIDC on, with realms for `pilot`, `dormant` and `gone` (not `norealm`). The settings object is frozen, so
    the oidc module gets a copy with the fields it reads overridden."""
    monkeypatch.setattr(
        oidc,
        "settings",
        replace(settings, oidc_issuer_base=ISSUER_BASE, oidc_client_id=CLIENT_ID, oidc_realms="pilot,dormant,gone"),
    )


@pytest.fixture
def realm(oidc_settings, monkeypatch):
    pytest.importorskip("cryptography", reason="PyJWT needs cryptography (PyJWT[crypto]) to sign and verify RS256")
    r = Realm()
    oidc.jwks.clear()
    monkeypatch.setattr(oidc.jwks, "fetch", r.fetch)
    yield r
    oidc.jwks.clear()
