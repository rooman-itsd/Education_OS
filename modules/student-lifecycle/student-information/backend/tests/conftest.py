"""Test fixtures for student-information."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/student_info_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest  # noqa: E402
from eos_core.db import Base, SessionLocal, engine, init_db  # noqa: E402
from eos_student_information.application.service import Actor  # noqa: E402
from eos_student_information.infrastructure.models import MODELS  # noqa: E402, F401


@pytest.fixture(scope="session", autouse=True)
def setup_database():
    """Create all core and module tables once for the test session."""
    init_db()
    Base.metadata.create_all(engine)


@pytest.fixture
def db():
    """Provides a fresh transactional session for each test, rolling back on completion."""
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
def actor_a():
    from eos_core.db import new_id

    return Actor(
        user_id="user-staff-a",
        organisation_id=f"org-a-{new_id()[:8]}",
        roles=["staff"],
        permissions={
            "student-information:person:read",
            "student-information:person:write",
            "student-information:status:manage",
            "student-information:document:manage",
            "student-information:id-card:manage",
        },
    )


@pytest.fixture
def actor_b():
    from eos_core.db import new_id

    return Actor(
        user_id="user-staff-b",
        organisation_id=f"org-b-{new_id()[:8]}",
        roles=["staff"],
        permissions={
            "student-information:person:read",
            "student-information:person:write",
            "student-information:status:manage",
            "student-information:document:manage",
            "student-information:id-card:manage",
        },
    )


ALL_PERMISSIONS = {
    "student-information:person:read",
    "student-information:person:write",
    "student-information:status:manage",
    "student-information:document:manage",
    "student-information:id-card:manage",
}

BASE_PATH = "/api/v1/student-information"

# Roles from contracts/permissions.yaml: tokens carry roles, as identity issues them; permissions come from
# the catalogue (eos_core.config.permissions_for), never from a claim.
REGISTRAR = "registrar"  # every student-information key
READ_ONLY = "management"  # person:read only
ADMISSIONS = "admissions-staff"  # person:read and person:write
NO_ACCESS = "student"  # no student-information key


@pytest.fixture(scope="session")
def app():
    from eos_student_information.api.router import router
    from fastapi import FastAPI

    application = FastAPI(title="Student Information Test API")
    application.include_router(router, prefix=BASE_PATH)
    return application


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def mint_token(
    *,
    user_id: str = "test-user-1",
    organisation_id: str | None = None,
    roles: list[str] | None = None,
    sa: bool = False,
    secret: str | None = None,
) -> str:
    from datetime import timedelta

    import jwt
    from eos_core.db import utcnow
    from eos_core.settings import settings

    now = utcnow()
    payload = {
        "sub": user_id,
        "org": organisation_id,
        "roles": roles or [],
        "sa": sa,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm="HS256")


def make_auth_headers(
    *,
    user_id: str = "test-user-1",
    organisation_id: str | None = None,
    roles: list[str] | None = None,
    sa: bool = False,
    secret: str | None = None,
) -> dict[str, str]:
    token = mint_token(
        user_id=user_id,
        organisation_id=organisation_id,
        roles=roles,
        sa=sa,
        secret=secret,
    )
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def headers_a():
    from eos_core.db import new_id

    return make_auth_headers(
        user_id="user-staff-a",
        organisation_id=f"org-a-{new_id()[:8]}",
        roles=[REGISTRAR],
    )


@pytest.fixture
def headers_b():
    from eos_core.db import new_id

    return make_auth_headers(
        user_id="user-staff-b",
        organisation_id=f"org-b-{new_id()[:8]}",
        roles=[REGISTRAR],
    )
