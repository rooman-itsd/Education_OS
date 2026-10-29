"""Test fixtures for admissions. The database URL must be set before eos_core is imported: eos_core.db builds
its engine at import time. Every test uses fresh organisation ids, so tests never see each other's rows."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/admissions_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

from datetime import timedelta  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from eos_admissions.application.service import Actor  # noqa: E402
from eos_admissions.domain import enums as e  # noqa: E402
from eos_admissions.infrastructure.models import (  # noqa: E402
    TABLES,
    Application,
    ApplicationDocument,
    Offer,
)
from eos_core.db import Base, SessionLocal, engine, init_db, new_id, utcnow  # noqa: E402
from eos_core.settings import settings  # noqa: E402
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

BASE = "/api/v1/admissions"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"

# Roles from the repo's permission catalogue; tokens carry roles, permissions come from the catalogue.
STAFF = "admissions-staff"  # every admissions key
REVIEWER = "admissions-reviewer"  # application:read, document:verify
MANAGEMENT = "management"  # report:read only
NO_ACCESS = "student"  # no admissions key

ALL_PERMISSIONS = {
    "admissions:application:read",
    "admissions:application:manage",
    "admissions:document:verify",
    "admissions:merit-list:manage",
    "admissions:offer:manage",
    "admissions:report:read",
}


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
    """A session on its own empty database with only the admissions tables, for constraint tests that need
    a real commit and rollback."""
    own_engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/admissions_constraints.db")
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


def make_actor(organisation_id: str, permissions: set[str] | None = None, user_id: str | None = None) -> Actor:
    return Actor(
        user_id=user_id or new_id(),
        organisation_id=organisation_id,
        roles=[STAFF],
        permissions=ALL_PERMISSIONS if permissions is None else permissions,
    )


@pytest.fixture
def staff(org) -> Actor:
    return make_actor(org)


# ---------------------------------------------------------------- HTTP


# Stands in for the host gateway, which resolves /public/{org_slug}/ to an organisation (or answers 404).
SLUGS: dict[str, str] = {}


def public_slug(organisation_id: str) -> str:
    slug = f"org-{organisation_id[:8]}"
    SLUGS[slug] = organisation_id
    return slug


@pytest.fixture(scope="session")
def app():
    from eos_admissions.api.deps import public_organisation
    from eos_admissions.api.router import router
    from eos_core.db import get_db
    from fastapi import Depends, FastAPI, HTTPException

    def resolved_by_test_gateway(org_slug: str, db: Session = Depends(get_db)) -> str:
        if org_slug not in SLUGS:
            raise HTTPException(404, {"code": "unknown_organisation", "message": "unknown"})
        db.info["organisation_id"] = SLUGS[org_slug]
        return SLUGS[org_slug]

    application = FastAPI()
    application.include_router(router, prefix=BASE)
    application.dependency_overrides[public_organisation] = resolved_by_test_gateway
    return application


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def mint_token(organisation_id: str | None, roles: list[str], user_id: str = "user-1", secret: str | None = None):
    now = utcnow()
    claims = {
        "sub": user_id,
        "org": organisation_id,
        "roles": roles,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(claims, secret or settings.jwt_secret, algorithm="HS256")


def headers(organisation_id: str | None, role: str = STAFF, user_id: str = "user-1") -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_token(organisation_id, [role], user_id)}"}


# ---------------------------------------------------------------- data


def add_application(session: Session, organisation_id: str, **overrides) -> Application:
    values = {
        "organisation_id": organisation_id,
        "reference_number": f"ADM-2026-{new_id()[:6].upper()}",
        "applicant_first_name": "Ana",
        "applicant_last_name": "Silva",
        "applicant_email": "ana@example.com",
        "programme_id": new_id(),
        "academic_year": "2026-27",
        "status": e.SUBMITTED,
    }
    application = Application(**values | overrides)
    session.add(application)
    session.flush()
    return application


def add_document(session: Session, application: Application, **overrides) -> ApplicationDocument:
    values = {
        "organisation_id": application.organisation_id,
        "application_id": application.id,
        "type": "academic_record",
        "document_id": new_id(),
    }
    document = ApplicationDocument(**values | overrides)
    session.add(document)
    session.flush()
    return document


def add_offer(session: Session, application: Application, **overrides) -> Offer:
    values = {
        "organisation_id": application.organisation_id,
        "application_id": application.id,
        "status": e.OFFER_OPEN,
        "offered_by": "staff-1",
    }
    offer = Offer(**values | overrides)
    session.add(offer)
    session.flush()
    return offer


def seed(fn, *args, **kwargs):
    """Create rows through the app's own session factory and commit, for HTTP tests. Returns the row's id."""
    with SessionLocal() as session:
        row = fn(session, *args, **kwargs)
        session.commit()
        return row.id
