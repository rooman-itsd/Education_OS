"""Test fixtures for web-portal-cms. The database URL must be set before eos_core is imported: eos_core.db builds its
engine at import time. Every test uses fresh organisation ids, so tests never see each other's rows."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/web_portal_cms_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

from datetime import timedelta  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from eos_core.db import Base, SessionLocal, engine, init_db, new_id, utcnow  # noqa: E402
from eos_core.settings import settings  # noqa: E402
from eos_web_portal_cms.application.service import Actor  # noqa: E402
from eos_web_portal_cms.infrastructure.models import TABLES, Announcement, Page  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

BASE = "/api/v1/web-portal-cms"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"

EDITOR = "web-portal-cms-editor"  # every key
ORG_ADMIN = "org-admin"  # every key
APPLICANT = "applicant"  # read keys only, through the implicit member role

READ = {"web-portal-cms:page:read", "web-portal-cms:announcement:read"}
ALL = READ | {"web-portal-cms:page:manage", "web-portal-cms:announcement:manage"}


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    init_db()
    Base.metadata.create_all(engine)


@pytest.fixture
def db():
    """A session whose work is rolled back after the test."""
    connection = engine.connect()
    transaction = connection.begin()
    session = SessionLocal(bind=connection)
    try:
        yield session
    finally:
        session.close()
        if transaction.is_active:
            transaction.rollback()
        connection.close()


@pytest.fixture
def fresh_db():
    """A session on its own empty database with only this module's tables, for constraint tests."""
    own_engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/web_portal_cms_constraints.db")
    Base.metadata.create_all(own_engine, tables=TABLES)
    session = Session(own_engine)
    try:
        yield session
    finally:
        session.close()
        own_engine.dispose()


@pytest.fixture
def org() -> str:
    return new_id()


@pytest.fixture
def other_org() -> str:
    return new_id()


def make_actor(organisation_id: str, permissions: set[str] | None = None) -> Actor:
    return Actor(
        user_id=new_id(), organisation_id=organisation_id, permissions=ALL if permissions is None else permissions
    )


@pytest.fixture
def editor(org) -> Actor:
    return make_actor(org)


@pytest.fixture
def reader(org) -> Actor:
    return make_actor(org, READ)


# ---------------------------------------------------------------- HTTP


@pytest.fixture(scope="session")
def app():
    from eos_web_portal_cms.api.router import router
    from fastapi import FastAPI

    application = FastAPI()
    application.include_router(router, prefix=BASE)
    return application


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def mint_token(organisation_id: str | None, roles: list[str], secret: str | None = None) -> str:
    now = utcnow()
    claims = {
        "sub": "user-1",
        "org": organisation_id,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(claims, secret or settings.jwt_secret, algorithm="HS256")


def headers(organisation_id: str | None, role: str = EDITOR) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_token(organisation_id, [role])}"}


# ---------------------------------------------------------------- data


def add_page(session: Session, organisation_id: str, **overrides) -> Page:
    now = utcnow()
    values = {
        "organisation_id": organisation_id,
        "slug": f"page-{new_id()[:8]}",
        "title": "About us",
        "type": "standard",
        "body": "Line one\nLine two",
        "published": True,
        "published_at": now,
        "created_by": "u",
        "updated_by": "u",
        "created_at": now,
        "updated_at": now,
    }
    row = Page(**values | overrides)
    session.add(row)
    session.flush()
    return row


def add_announcement(session: Session, organisation_id: str, **overrides) -> Announcement:
    now = utcnow()
    values = {
        "organisation_id": organisation_id,
        "title": "Admissions open",
        "body": "Apply by 30 November.",
        "published": True,
        "published_at": now,
        "created_by": "u",
        "updated_by": "u",
        "created_at": now,
        "updated_at": now,
    }
    row = Announcement(**values | overrides)
    session.add(row)
    session.flush()
    return row


def seed(fn, *args, **kwargs):
    """Create a row through the app's own session factory and commit, for HTTP tests. Returns the detached row."""
    with SessionLocal() as session:
        row = fn(session, *args, **kwargs)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row
