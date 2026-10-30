"""tenancy's tests run alone (module standard rule 6): eos_core, eos_testing, this package and the two platform
services it declares (identity, billing). The database is a throwaway SQLite file; EOS_DATABASE_URL is overwritten,
not defaulted, so a shell pointing at a real database can never be reached from here."""

import os
import tempfile
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/tenancy_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("BILLING_PAYMENT_ADAPTER", "none")
os.environ.setdefault("TENANCY_AUTO_APPROVE", "true")

import pytest
from eos_billing.application.service import seed_plans
from eos_core.db import SessionLocal, init_db
from eos_core.security import create_token
from eos_identity.api.router import router as identity_router
from eos_identity.application import service as identity
from eos_tenancy.api.router import router as tenancy_router
from eos_tenancy.application import service as tenancy
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from fastapi import FastAPI
from fastapi.testclient import TestClient

SA_EMAIL, SA_PASSWORD = "root@platform.example.com", "RootPassw0rd!"


@pytest.fixture(scope="session")
def client():
    app = FastAPI()
    app.include_router(identity_router, prefix="/api/v1/identity")
    app.include_router(tenancy_router, prefix="/api/v1/tenancy")
    init_db()
    # the host wires these at startup (apps/backend/main.py); the module's tests wire them the same way
    identity.hooks.status = tenancy.organisation_status
    identity.hooks.id_for_slug = tenancy.organisation_id_for_slug
    with SessionLocal() as db:
        seed_plans(db)
        identity.create_user(
            db, organisation_id=None, email=SA_EMAIL, name="Root", password=SA_PASSWORD, roles=[], is_super_admin=True
        )
        db.commit()
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def super_admin(client) -> dict:
    r = client.post("/api/v1/identity/auth/login", json={"email": SA_EMAIL, "password": SA_PASSWORD})
    assert r.status_code == 200, r.text
    return auth(r.json()["token"])


def organisation(client, slug: str, academy_type: str = "music-academy") -> dict:
    """A registered, active organisation with its admin logged in: {org, token, email, password, headers}."""
    a = register_and_login(client, slug=slug, academy_type=academy_type)
    return {**a, "headers": auth(a["token"])}


def token_for(user_id: str, organisation_id: str | None, roles: list[str], super_admin: bool = False) -> dict:
    return auth(create_token(user_id=user_id, organisation_id=organisation_id, roles=roles, super_admin=super_admin))
