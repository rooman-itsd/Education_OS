"""Test fixtures for reporting service."""

from __future__ import annotations

import os
import tempfile
import uuid
from collections.abc import Generator
from pathlib import Path

os.environ.setdefault("EOS_DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/reporting-test.db")
os.environ.setdefault("EOS_DEV_MODE", "true")
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[4]))

import pytest
from eos_core.db import SessionLocal, init_db
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import organisation_scope, platform_scope

try:
    from eos_documents.domain.models import Document
    from eos_documents.infrastructure.storage import MemoryStorage, reset_storage
except (ImportError, ModuleNotFoundError):
    Document = None  # type: ignore[assignment]

    class MemoryStorage:  # type: ignore[no-redef]
        pass

    def reset_storage() -> None:
        pass


from eos_identity.application.service import create_user
from eos_reporting.application import service
from eos_reporting.domain.models import MetricSnapshot, ReportDefinition, ReportExecution
from fastapi import FastAPI
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
        s.execute(delete(ReportExecution))
        s.execute(delete(ReportDefinition))
        s.execute(delete(MetricSnapshot))
        if Document is not None:
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
    return MemoryStorage()


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
    def __init__(self, db: Session, org_id: str | None = None, seed: bool = True):
        self.id = org_id or str(uuid.uuid4())
        with organisation_scope(self.id):
            if seed:
                service.ensure_standard_definitions(db, self.id)
                db.commit()
            self.admin = _create_test_user(db, self.id, ["org-admin"], "admin")
            self.dept_admin = _create_test_user(db, self.id, ["department-admin"], "dept-admin")
            self.management = _create_test_user(db, self.id, ["management"], "management")
            self.faculty = _create_test_user(db, self.id, ["faculty"], "faculty")
            self.student = _create_test_user(db, self.id, ["student"], "student")
        self.admin_id = self.admin.id
        self.dept_admin_id = self.dept_admin.id
        self.management_id = self.management.id
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
    def dept_admin_headers(self) -> dict[str, str]:
        return self.auth_headers(self.dept_admin)

    @property
    def management_headers(self) -> dict[str, str]:
        return self.auth_headers(self.management)

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
def unseeded_org(db: Session) -> OrgHelper:
    """A fresh organisation with no report definitions, as after provisioning."""
    return OrgHelper(db, seed=False)


@pytest.fixture
def client() -> TestClient:
    from eos_reporting.api.router import router

    app = FastAPI()
    app.include_router(router, prefix="/api/v1/reporting")
    return TestClient(app)
