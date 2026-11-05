"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package. Set before
eos_core is imported: the database is always a throwaway SQLite file and tokens are signed with a test key. Both are
overwritten, not defaulted, so a shell that points at a real database or holds a real key can never be reached from
these tests.

Course offerings, instructor assignments and course registrations reach lms only through its consumers, so the
fixtures deliver those events the way the relay does, with payloads shaped as academic-management and
enrolment-registration publish them."""

import os
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/lms_test.db"
os.environ["EOS_JWT_SECRET"] = "lms-tests-only-not-a-real-key-of-32-bytes"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import organisation_scope
from eos_lms.api.router import router
from eos_lms.application import common
from eos_lms.application import consumers as cons
from eos_lms.infrastructure.models import AuditEntry
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

# A Thursday morning; every test works relative to it.
NOW = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
BASE = "/api/v1/lms"

ADMIN = "lms-admin"
VIEWER = "lms-viewer"
HEAD = "lms-department-head"
FACULTY = "faculty"  # holds lms-instructor through the faculty layout's module_roles
STUDENT = "student"  # holds lms-student through the student layout's module_roles


def at(days: float = 0, hours: float = 0) -> str:
    """An instant relative to NOW, as the API takes it."""
    return (NOW + timedelta(days=days, hours=hours)).isoformat()


@pytest.fixture(scope="session", autouse=True)
def database():
    """The throwaway SQLite database, created once, for every test (consumer tests need no client)."""
    init_db()


@pytest.fixture(scope="session")
def client(database):
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setattr(common, "clock", lambda: NOW)
    return NOW


def set_clock(monkeypatch, when: datetime) -> None:
    monkeypatch.setattr(common, "clock", lambda: when)


class FakeEvent:
    """The envelope the relay hands a handler: id, name, version, organisation_id, actor, occurred_at, payload."""

    def __init__(self, name, organisation_id, payload, *, event_id=None, occurred_at=None, version=1):
        self.id = event_id or new_id()
        self.name = name
        self.version = version
        self.organisation_id = organisation_id
        self.actor = None
        self.occurred_at = occurred_at or NOW
        self.payload = payload


def deliver(organisation_id, name, payload, **envelope) -> str:
    """Run a consumer the way the relay does: in its own session, in the event's organisation, committed after the
    handler returns and rolled back if it raises."""
    event = FakeEvent(name, organisation_id, payload, **envelope)
    with organisation_scope(organisation_id), SessionLocal() as db:
        try:
            outcome = cons.CONSUMERS[name](db, event)
            db.commit()
        except BaseException:
            db.rollback()
            raise
    return outcome


def offering_created(offering_id, *, period_id=None, department_id=None, code="CS101", title="Programming"):
    return {
        "course_offering_id": offering_id,
        "course_id": new_id(),
        "academic_period_id": period_id or new_id(),
        "programme_ids": [new_id()],
        "course_code": code,
        "course_title": title,
        "credits": 4,
        "course_type": "theory",
        "department_id": department_id or new_id(),
    }


def assignment_created(offering_id, faculty_id, *, assignment_id=None, section_id=None):
    return {
        "instructor_assignment_id": assignment_id or new_id(),
        "course_offering_id": offering_id,
        "section_id": section_id,
        "faculty_id": faculty_id,
        "role": "primary",
        "contact_hours": 3,
    }


def registration_confirmed(offering_id, person_id, section_id, *, registration_id=None, name="Test Student"):
    return {
        "registration_id": registration_id or new_id(),
        "person_id": person_id,
        "course_offering_id": offering_id,
        "section_id": section_id,
        "academic_period_id": new_id(),
        "registration_type": "regular",
        "student_name": name,
        "roll_number": "R-001",
        "confirmed_at": NOW.isoformat(),
    }


class Org:
    """One organisation with helpers to mint users holding roles."""

    def __init__(self) -> None:
        self.id = new_id()

    def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
        user_id = user_id or new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def org() -> Org:
    return Org()


@pytest.fixture
def other_org() -> Org:
    return Org()


def ok(response, status: int = 200):
    assert response.status_code == status, (response.status_code, response.text)
    return response.json()


class Course:
    """An organisation with one course offering (sections A and B), an instructor assigned to it, two students in A and
    one in B, an LMS administrator, a viewer and an active course space for the offering."""

    def __init__(self, client, org: Org, *, department_id: str | None = None, period_id: str | None = None) -> None:
        self.client, self.org = client, org
        self.offering, self.section_a, self.section_b = new_id(), new_id(), new_id()
        self.department = department_id or new_id()
        self.period = period_id or new_id()
        deliver(
            org.id,
            cons.OFFERING_CREATED,
            offering_created(self.offering, period_id=self.period, department_id=self.department),
        )
        _, self.admin = org.user(ADMIN)
        _, self.viewer = org.user(VIEWER)
        self.teacher_id, self.teacher = org.user(FACULTY)
        deliver(org.id, cons.ASSIGNMENT_CREATED, assignment_created(self.offering, self.teacher_id))
        self.student_id, self.student = self.enrol(self.section_a, "Asha")
        self.student2_id, self.student2 = self.enrol(self.section_a, "Bala")
        self.student_b_id, self.student_b = self.enrol(self.section_b, "Chitra")
        self.space = self.post("/course-spaces", {"course_offering_id": self.offering, "title": "Programming"}, 201)
        self.space = self.post(f"/course-spaces/{self.space['id']}/status", {"status": "active"})

    def enrol(self, section_id: str, name: str, role: str = STUDENT) -> tuple[str, dict]:
        person, headers = self.org.user(role)
        deliver(
            self.org.id,
            cons.REGISTRATION_CONFIRMED,
            registration_confirmed(self.offering, person, section_id, name=name),
        )
        return person, headers

    # requests
    def call(self, method: str, path: str, body=None, headers=None):
        return self.client.request(method, f"{BASE}{path}", json=body, headers=headers or self.admin)

    def post(self, path: str, body=None, status: int = 200, headers=None):
        return ok(self.call("POST", path, body, headers), status)

    def get(self, path: str, headers=None, status: int = 200):
        return ok(self.call("GET", path, None, headers), status)

    def patch(self, path: str, body, headers=None, status: int = 200):
        return ok(self.call("PATCH", path, body, headers), status)

    def put(self, path: str, body, headers=None, status: int = 200):
        return ok(self.call("PUT", path, body, headers), status)

    # content
    def material(self, title: str = "Week 1 notes", publish: bool = True, **over) -> dict:
        body = {"material_type": "page", "title": title, "body": "Read chapter 1", **over}
        m = self.post(f"/course-spaces/{self.space['id']}/materials", body, 201, self.teacher)
        if publish:
            m = self.post(f"/materials/{m['id']}/status", {"status": "published"}, headers=self.teacher)
        return m

    def assignment(self, publish: bool = True, **over) -> dict:
        body = {"title": "Essay 1", "due_at": at(days=7), "max_points": 10, "submission_type": "text", **over}
        x = self.post(f"/course-spaces/{self.space['id']}/assignments", body, 201, self.teacher)
        if publish:
            x = self.post(f"/assignments/{x['id']}/status", {"status": "published"}, headers=self.teacher)
        return x

    def quiz(self, publish: bool = True, questions: list[dict] | None = None, **over) -> dict:
        body = {
            "title": "Quiz 1",
            "opens_at": at(hours=-1),
            "closes_at": at(days=2),
            "attempts_allowed": 2,
            "questions": questions
            or [
                {
                    "question_type": "single_choice",
                    "prompt": "2+2?",
                    "options": ["3", "4"],
                    "answer_key": [1],
                    "points": 2,
                },
                {"question_type": "true_false", "prompt": "Sky is blue", "answer_key": True, "points": 1},
            ],
            **over,
        }
        qz = self.post(f"/course-spaces/{self.space['id']}/quizzes", body, 201, self.teacher)
        if publish:
            qz = self.post(f"/quizzes/{qz['id']}/status", {"status": "published"}, headers=self.teacher)
        return qz


@pytest.fixture
def course(client, org) -> Course:
    return Course(client, org)


def outbox(name: str, organisation_id: str) -> list[dict]:
    """Payloads of outbox events with this name for one organisation, oldest first."""
    with SessionLocal() as db:
        rows = db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
            .order_by(OutboxEvent.occurred_at, OutboxEvent.id)
        )
        return [r.payload for r in rows]


def all_events(organisation_id: str) -> list[OutboxEvent]:
    with SessionLocal() as db:
        return list(db.scalars(select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)))


def audit_actions(organisation_id: str, entity_id: str | None = None) -> list[str]:
    """The audited actions, sorted: under the frozen clock entries of one test share their time."""
    with SessionLocal() as db:
        query = select(AuditEntry).where(AuditEntry.organisation_id == organisation_id)
        if entity_id:
            query = query.where(AuditEntry.entity_id == entity_id)
        return sorted(r.action for r in db.scalars(query))
