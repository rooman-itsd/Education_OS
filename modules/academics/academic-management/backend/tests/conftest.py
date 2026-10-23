"""The module's tests run alone (module standard rule 6). Set before eos_core is imported: the database is always a
throwaway SQLite file and tokens are signed with a test key. Both are overwritten, not defaulted, so a shell that
points at a real database or holds a real key can never be reached from these tests.

The API fixtures below need eos_core (packages/core/src on PYTHONPATH). Without it, the domain and application
tests still run and the API tests are skipped."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/academic_management_test.db"
os.environ["EOS_JWT_SECRET"] = "academic-management-tests-only-not-a-real-key-32b"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

try:
    import eos_core  # noqa: F401
except ImportError:  # domain and application tests only
    eos_core = None

BASE = "/api/v1/academic-management"
NOW = datetime(2026, 10, 22, 9, 0, tzinfo=UTC)
FACULTY_NAMES: dict[str, str] = {}  # the test stand-in for the identity lookup (api.router.faculty_directory)

if eos_core is not None:
    from eos_academic_management.api.router import faculty_directory, router
    from eos_academic_management.application import service
    from eos_core.db import init_db, new_id
    from eos_core.security import create_token
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    @pytest.fixture(scope="session")
    def client():
        app = FastAPI()
        app.include_router(router, prefix=BASE)
        app.dependency_overrides[faculty_directory] = lambda: FACULTY_NAMES.__getitem__
        init_db()
        with TestClient(app) as c:
            yield c

    @pytest.fixture(autouse=True)
    def frozen_clock(monkeypatch):
        monkeypatch.setattr(service, "clock", lambda: NOW)
        return NOW

    class Org:
        """One organisation with helpers to mint users holding platform roles."""

        def __init__(self) -> None:
            self.id = new_id()

        def user(self, *roles: str, user_id: str | None = None, name: str | None = None) -> tuple[str, dict]:
            user_id = user_id or new_id()
            if name:
                FACULTY_NAMES[user_id] = name
            token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
            return user_id, {"Authorization": f"Bearer {token}"}

    @pytest.fixture
    def org() -> "Org":
        return Org()

    @pytest.fixture
    def other_org() -> "Org":
        return Org()

    # ------------------------------------------------------------ helpers that go through the real API

    def ok(response, status: int = 200) -> dict:
        assert response.status_code == status, (response.status_code, response.text)
        return response.json()

    def make_term(client, h, code="2026-ODD", start="2026-07-01", end="2026-11-30") -> dict:
        body = {"code": code, "name": f"Term {code}", "starts_on": start, "ends_on": end}
        return ok(client.post(f"{BASE}/terms", json=body, headers=h), 201)

    def make_course(client, h, code="CS101", credits=4, department_id=None) -> dict:
        body = {"code": code, "title": f"Course {code}", "credits": credits, "course_type": "theory"}
        body["department_id"] = department_id or new_id()
        return ok(client.post(f"{BASE}/courses", json=body, headers=h), 201)

    def make_programme(client, h, code="BSC-CS", duration_terms=2, credits_required=8) -> dict:
        body = {
            "code": code,
            "name": f"Programme {code}",
            "level": "undergraduate",
            "department_id": new_id(),
            "duration_terms": duration_terms,
            "credits_required": credits_required,
        }
        return ok(client.post(f"{BASE}/programmes", json=body, headers=h), 201)

    def make_offering(client, h, course_id, term_id, sections=(("A", 2),)) -> dict:
        body = {
            "course_id": course_id,
            "academic_period_id": term_id,
            "sections": [{"code": c, "capacity": n} for c, n in sections],
        }
        return ok(client.post(f"{BASE}/offerings", json=body, headers=h), 201)

    def assign(client, h, offering_id, faculty_id, role="primary", hours=4, section_id=None) -> dict:
        body = {"faculty_id": faculty_id, "role": role, "contact_hours": hours}
        if section_id:
            body["section_id"] = section_id
        return ok(client.post(f"{BASE}/offerings/{offering_id}/faculty-assignments", json=body, headers=h), 201)

    def open_offering(client, h, offering_id, faculty_id) -> dict:
        assign(client, h, offering_id, faculty_id)
        return ok(client.post(f"{BASE}/offerings/{offering_id}/status", json={"status": "open"}, headers=h))

    def outbox(organisation_id: str, prefix: str = "academic-management.") -> list:
        """Outbox rows of one organisation, oldest first (eos_core.events.OutboxEvent)."""
        from eos_core.db import SessionLocal
        from eos_core.events import OutboxEvent
        from sqlalchemy import select

        with SessionLocal() as db:
            rows = db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.organisation_id == organisation_id, OutboxEvent.name.startswith(prefix))
                .order_by(OutboxEvent.occurred_at)
            )
            return [(r.name, dict(r.payload), r.actor) for r in rows]
