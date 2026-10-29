"""Test fixtures for enrolment-registration. The database URL must be set before eos_core is imported: eos_core.db
builds its engine at import time. Every test uses fresh organisation ids, so tests never see each other's rows."""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/enrolment_registration_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

from datetime import timedelta  # noqa: E402

import jwt  # noqa: E402
import pytest  # noqa: E402
from eos_core.db import Base, SessionLocal, engine, init_db, new_id, utcnow  # noqa: E402
from eos_core.settings import settings  # noqa: E402
from eos_enrolment_registration.application.service import Actor  # noqa: E402
from eos_enrolment_registration.domain import enums as e  # noqa: E402
from eos_enrolment_registration.infrastructure.models import (  # noqa: E402
    TABLES,
    OfferingRef,
    ProgrammeEnrolment,
    RegistrationWindow,
    SectionRef,
    TermRef,
)
from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

BASE = "/api/v1/enrolment-registration"
CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"

# Roles from the repo's permission catalogue; tokens carry roles, permissions come from the catalogue.
STAFF = "registration-staff"  # every key
EXAM_STAFF = "examination-staff"  # registration:read
MANAGEMENT = "management"  # both read keys
NO_ACCESS = "student"  # no enrolment-registration key

ALL_PERMISSIONS = {
    "enrolment-registration:enrolment:read",
    "enrolment-registration:enrolment:manage",
    "enrolment-registration:registration:read",
    "enrolment-registration:registration:manage",
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
    """A session on its own empty database with only this module's tables, for constraint tests that need a real
    commit and rollback."""
    own_engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}/enrolment_registration_constraints.db")
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
        user_id=new_id(),
        organisation_id=organisation_id,
        roles=[STAFF],
        permissions=ALL_PERMISSIONS if permissions is None else permissions,
    )


@pytest.fixture
def staff(org) -> Actor:
    return make_actor(org)


# ---------------------------------------------------------------- HTTP


@pytest.fixture(scope="session")
def app():
    from eos_enrolment_registration.api.router import router
    from fastapi import FastAPI

    application = FastAPI()
    application.include_router(router, prefix=BASE)
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


def headers(organisation_id: str | None, role: str = STAFF) -> dict[str, str]:
    return {"Authorization": f"Bearer {mint_token(organisation_id, [role])}"}


# ---------------------------------------------------------------- data


def add_enrolment(session: Session, organisation_id: str, **overrides) -> ProgrammeEnrolment:
    values = {
        "organisation_id": organisation_id,
        "person_id": new_id(),
        "student_name": "Ana Silva",
        "programme_id": new_id(),
        "roll_number": f"RN2026-{new_id()[:8]}",
        "start_academic_period_id": new_id(),
        "status": e.ACTIVE,
        "enrolled_by": "staff-1",
    }
    row = ProgrammeEnrolment(**values | overrides)
    session.add(row)
    session.flush()
    return row


def add_window(session: Session, organisation_id: str, term: str, open_now: bool = True) -> RegistrationWindow:
    now = utcnow()
    opens, closes = (
        (now - timedelta(days=1), now + timedelta(days=1))
        if open_now
        else (
            now - timedelta(days=3),
            now - timedelta(days=1),
        )
    )
    row = RegistrationWindow(
        organisation_id=organisation_id, academic_period_id=term, opens_at=opens, closes_at=closes, updated_by="s"
    )
    session.add(row)
    session.flush()
    return row


def add_offering(session: Session, organisation_id: str, term: str, status: str = e.OPEN, **over) -> OfferingRef:
    values = {
        "course_offering_id": new_id(),
        "organisation_id": organisation_id,
        "academic_period_id": term,
        "course_code": "CS101",
        "course_title": "Programming I",
        "status": status,
    }
    row = OfferingRef(**values | over)
    session.add(row)
    session.flush()
    return row


def add_section(session: Session, offering: OfferingRef, capacity: int = 30, status: str = e.OPEN) -> SectionRef:
    row = SectionRef(
        section_id=new_id(),
        organisation_id=offering.organisation_id,
        course_offering_id=offering.course_offering_id,
        code="A",
        capacity=capacity,
        status=status,
    )
    session.add(row)
    session.flush()
    return row


def add_term(session: Session, organisation_id: str, active: bool = True, **over) -> TermRef:
    values = {"academic_period_id": new_id(), "organisation_id": organisation_id, "name": "Term 1", "is_active": active}
    row = TermRef(**values | over)
    session.add(row)
    session.flush()
    return row


def seed(fn, *args, **kwargs):
    """Create rows through the app's own session factory and commit, for HTTP tests. Returns the row."""
    with SessionLocal() as session:
        row = fn(session, *args, **kwargs)
        session.commit()
        session.refresh(row)
        session.expunge(row)
        return row
