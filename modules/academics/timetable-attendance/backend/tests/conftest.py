"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. Set before
eos_core is imported: the database is always a throwaway SQLite file and tokens are signed with a test key. Both are
overwritten, not defaulted, so a shell that points at a real database or holds a real key can never be reached from
these tests.

The API fixtures below need eos_core (packages/core/src on PYTHONPATH). Without it, the domain tests still run and the
API tests are skipped."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

import pytest

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/timetable_attendance_test.db"
os.environ["EOS_JWT_SECRET"] = "timetable-attendance-tests-only-not-a-real-key-32b"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

try:
    import eos_core  # noqa: F401
except ImportError:  # domain tests only
    eos_core = None

BASE = "/api/v1/timetable-attendance"
NOW = datetime(2026, 11, 3, 9, 0, tzinfo=UTC)

ADMIN = "timetable-attendance-admin"  # reads and writes timetables
HEAD = "timetable-attendance-department-head"  # reads and writes timetables
FACULTY = "timetable-attendance-faculty"  # reads timetables, no write
STUDENT = "timetable-attendance-student"  # no timetable key at all

if eos_core is not None:
    from eos_core.db import SessionLocal, init_db, new_id
    from eos_core.security import create_token
    from eos_timetable_attendance.api.router import router
    from eos_timetable_attendance.application import service
    from eos_timetable_attendance.infrastructure.models import AssignmentRef, OfferingRef, SectionRef
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

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
        """One organisation with helpers to mint users holding roles and to fill its academic-management read models."""

        def __init__(self) -> None:
            self.id = new_id()

        def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
            user_id = user_id or new_id()
            token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
            return user_id, {"Authorization": f"Bearer {token}"}

        def academic(self, *, period_id: str | None = None, instructor_id: str | None = None) -> dict:
            """One course offering with a section and an instructor assignment to the whole offering, as the (not yet
            wired) consumers would write them. The read models have no API, so the test writes the rows."""
            ids = {
                "period": period_id or new_id(),
                "offering": new_id(),
                "section": new_id(),
                "assignment": new_id(),
                "instructor": instructor_id or new_id(),
            }
            with SessionLocal() as db:
                db.add(
                    OfferingRef(
                        organisation_id=self.id,
                        course_offering_id=ids["offering"],
                        academic_period_id=ids["period"],
                        course_code="CS101",
                        course_title="Programming",
                        status="open",
                    )
                )
                db.add(
                    SectionRef(
                        organisation_id=self.id,
                        section_id=ids["section"],
                        course_offering_id=ids["offering"],
                        code="A",
                        status="open",
                    )
                )
                db.add(
                    AssignmentRef(
                        organisation_id=self.id,
                        instructor_assignment_id=ids["assignment"],
                        course_offering_id=ids["offering"],
                        section_id=None,
                        instructor_id=ids["instructor"],
                        status="active",
                    )
                )
                db.commit()
            return ids

    @pytest.fixture
    def org() -> Org:
        return Org()

    @pytest.fixture
    def other_org() -> Org:
        return Org()

    # ------------------------------------------------------------ helpers that go through the real API

    def ok(response, status: int = 200) -> dict:
        assert response.status_code == status, (response.status_code, response.text)
        return response.json()

    def slot(ids: dict, day: str = "monday", start: str = "09:00:00", end: str = "10:00:00", **over) -> dict:
        body = {
            "day_of_week": day,
            "start_time": start,
            "end_time": end,
            "course_offering_id": ids["offering"],
            "section_id": ids["section"],
            "instructor_assignment_id": ids["assignment"],
        }
        return {**body, **over}

    def make_timetable(client, headers, period_id: str | None = None, name: str = "Odd term", **over) -> dict:
        body = {"academic_period_id": period_id or new_id(), "name": name, **over}
        return ok(client.post(f"{BASE}/timetables", json=body, headers=headers), 201)

    def audit_entries(organisation_id: str, entity_id: str | None = None) -> list:
        from eos_timetable_attendance.infrastructure import repository as repo
        from eos_timetable_attendance.infrastructure.models import AuditEntry

        with SessionLocal() as db:
            db.info["organisation_id"] = organisation_id
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
