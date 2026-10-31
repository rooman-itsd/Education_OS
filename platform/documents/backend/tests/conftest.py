"""Test fixtures for documents service."""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/documents-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope
from eos_documents.domain.models import Document
from eos_documents.infrastructure.storage import MemoryStorage, reset_storage
from eos_identity.application.service import create_user
from fastapi.testclient import TestClient
from sqlalchemy import delete
from sqlalchemy.orm import Session


@pytest.fixture(scope="session", autouse=True)
def _setup_db():
    init_db()


@pytest.fixture(autouse=True)
def _clean_tables():
    with platform_scope(), SessionLocal() as s:
        if s.get_bind().dialect.name != "sqlite":
            return
        s.execute(delete(Document))
        s.execute(delete(OutboxEvent))
        s.commit()


@pytest.fixture(autouse=True)
def _reset_storage_singleton():
    reset_storage()
    yield
    reset_storage()


@pytest.fixture
def memory_storage() -> MemoryStorage:
    storage = MemoryStorage()
    return storage


@pytest.fixture
def db() -> Generator[Session, None, None]:
    with SessionLocal() as session:
        yield session


def _create_test_user(db: Session, org_id: str, roles: list[str], label: str):
    user = create_user(
        db,
        organisation_id=org_id,
        email=f"{label}-{uuid.uuid4().hex[:8]}@example.com",
        name=label,
        password="Secret123!",
        roles=roles,
    )
    db.commit()
    return user


class OrgHelper:
    def __init__(self, db: Session, org_id: str | None = None):
        self.id = org_id or str(uuid.uuid4())
        with organisation_scope(self.id):
            self.admin = _create_test_user(db, self.id, ["org-admin"], "admin")
            self.faculty = _create_test_user(db, self.id, ["faculty"], "faculty")
            self.student = _create_test_user(db, self.id, ["student"], "student")
        self.admin_id = self.admin.id
        self.faculty_id = self.faculty.id
        self.student_id = self.student.id

    def auth_headers(self, user) -> dict[str, str]:
        token = create_token(
            user_id=user.id,
            organisation_id=self.id,
            roles=list(user.roles),
        )
        return {"Authorization": f"Bearer {token}"}

    @property
    def admin_headers(self) -> dict[str, str]:
        return self.auth_headers(self.admin)

    @property
    def faculty_headers(self) -> dict[str, str]:
        return self.auth_headers(self.faculty)

    @property
    def student_headers(self) -> dict[str, str]:
        return self.auth_headers(self.student)


@pytest.fixture
def org(db: Session) -> OrgHelper:
    return OrgHelper(db)


@pytest.fixture
def other_org(db: Session) -> OrgHelper:
    return OrgHelper(db)


@pytest.fixture
def client() -> TestClient:
    from eos_documents.api.router import router
    from fastapi import FastAPI

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/documents")
    return TestClient(app)
