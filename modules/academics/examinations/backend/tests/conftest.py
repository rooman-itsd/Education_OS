"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. Set before eos_core
is imported: the database is always a throwaway SQLite file and tokens are signed with a test key. Both are overwritten,
not defaulted, so a shell that points at a real database or holds a real key can never be reached from these tests."""

import os
import tempfile
import uuid
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/examinations_test.db"
os.environ["EOS_JWT_SECRET"] = "examinations-tests-only-not-a-real-key-32-bytes"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))


def uid() -> str:
    return str(uuid.uuid4())


BASE = "/api/v1/examinations"
CONTROLLER = "examinations-controller"  # every key of the 15 operations
HEAD = "examinations-department-head"  # reads; assessment-scheme write-department only
FACULTY = "examinations-faculty"  # reads cycles and assessment schemes; no grading-scheme key, no write
VIEWER = "examinations-viewer"  # reads only
STUDENT = "examinations-student"  # none of the keys of these operations

try:
    import eos_core  # noqa: F401
except ImportError:  # domain tests only
    eos_core = None

if eos_core is not None:
    from datetime import UTC, datetime

    import pytest
    from eos_core.db import SessionLocal, init_db
    from eos_core.security import create_token
    from eos_examinations.api.router import router
    from eos_examinations.application import service
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)

    @pytest.fixture(scope="session")
    def client():
        app = FastAPI()
        app.include_router(router, prefix=BASE)
        init_db()
        with TestClient(app) as c:
            yield c

    @pytest.fixture(autouse=True)
    def frozen_clock(monkeypatch):
        monkeypatch.setattr(service, "clock", lambda: NOW)
        return NOW

    class Org:
        """One organisation with a helper to mint users holding roles."""

        def __init__(self) -> None:
            self.id = uid()

        def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
            user_id = user_id or uid()
            token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
            return user_id, {"Authorization": f"Bearer {token}"}

        def controller(self) -> dict:
            return self.user(CONTROLLER)[1]

    @pytest.fixture
    def org() -> Org:
        return Org()

    @pytest.fixture
    def other_org() -> Org:
        return Org()

    @pytest.fixture
    def h(org) -> dict:
        """Headers of an examinations controller of `org`."""
        return org.controller()

    def ok(response, status: int = 200):
        assert response.status_code == status, (response.status_code, response.text)
        return response.json()

    def err(response, status: int, code: str) -> dict:
        assert response.status_code == status, (response.status_code, response.text)
        detail = response.json()["detail"]
        assert detail["code"] == code, detail
        return detail

    BANDS = [
        {"min_percent": 0, "max_percent": 40, "grade": "F", "grade_point": 0, "is_pass": False},
        {"min_percent": 40, "max_percent": 100, "grade": "P", "grade_point": 6, "is_pass": True},
    ]

    def grading_body(name="10 point", bands=None) -> dict:
        return {"name": name, "bands": [dict(b) for b in (BANDS if bands is None else bands)]}

    def make_grading(client, headers, name="10 point", bands=None) -> dict:
        return ok(client.post(f"{BASE}/grading-schemes", json=grading_body(name, bands), headers=headers), 201)

    def component(code="END", weightage=100, **over) -> dict:
        return {
            "code": code,
            "name": f"{code} exam",
            "kind": "written",
            "weightage_percent": weightage,
            "max_marks": 100,
            **over,
        }

    def assessment_body(offering_id=None, components=None, pass_percent=40) -> dict:
        return {
            "course_offering_id": offering_id or uid(),
            "pass_percent": pass_percent,
            "components": [component()] if components is None else components,
        }

    def make_assessment(client, headers, offering_id=None, components=None, pass_percent=40) -> dict:
        body = assessment_body(offering_id, components, pass_percent)
        return ok(client.post(f"{BASE}/assessment-schemes", json=body, headers=headers), 201)

    def cycle_body(**over) -> dict:
        body = {
            "academic_period_id": uid(),
            "code": "2026-ODD-END",
            "name": "Odd semester end term",
            "cycle_type": "end_term",
            "starts_on": "2026-11-20",
            "ends_on": "2026-12-10",
        }
        return {**body, **over}

    def make_cycle(client, headers, grading_scheme_id: str | None = None, **over) -> dict:
        if grading_scheme_id:
            over["grading_scheme_id"] = grading_scheme_id
        return ok(client.post(f"{BASE}/exam-cycles", json=cycle_body(**over), headers=headers), 201)

    def session_for(organisation_id: str):
        db = SessionLocal()
        db.info["organisation_id"] = organisation_id
        return db

    def audit_entries(organisation_id: str, entity_id: str | None = None) -> list:
        from eos_examinations.infrastructure import repository as repo
        from eos_examinations.infrastructure.models import AuditEntry

        with session_for(organisation_id) as db:
            query = repo.q(db, AuditEntry)
            if entity_id:
                query = query.where(AuditEntry.entity_id == entity_id)
            return list(db.scalars(query.order_by(AuditEntry.occurred_at, AuditEntry.id)))

    def outbox(name: str, organisation_id: str) -> list[dict]:
        """Payloads of outbox events with this name for one organisation, oldest first."""
        from eos_core.events import OutboxEvent
        from sqlalchemy import select

        with SessionLocal() as db:
            rows = db.scalars(
                select(OutboxEvent)
                .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
                .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
            )
            return [r.payload for r in rows]

    def all_outbox(organisation_id: str) -> list[str]:
        from eos_core.events import OutboxEvent
        from sqlalchemy import select

        with SessionLocal() as db:
            return [
                r.name for r in db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id))
            ]
