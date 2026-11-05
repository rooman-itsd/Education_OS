"""Helpers shared by the alumni tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

BASE = "/api/v1/alumni"
NOW = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)  # 11:30 on 3 November in Asia/Kolkata
TODAY = "2026-11-03"


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def iso(moment: datetime) -> str:
    return moment.astimezone(UTC).isoformat()


class Clock:
    """The service's clock, moved by tests."""

    def __init__(self):
        self.now = NOW

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now = self.now + timedelta(**delta)


class Org:
    """An organisation with one user per role. The placement officer holds alumni-coordinator and the management
    student alumni-mentee through their layouts' module_roles (management-institute); faculty and a user with no role
    hold no alumni key. `ids` gives chosen user ids, e.g. the same student id in two organisations."""

    ROLES = {
        "coord": ["placement-officer"],
        "student": ["management-student"],
        "student2": ["management-student"],
        "faculty": ["faculty"],
        "nobody": [],
    }

    def __init__(self, ids: dict[str, str] | None = None):
        self.id = new_id()
        self.ids: dict[str, str] = {}
        self.headers: dict[str, dict] = {}
        for name, roles in self.ROLES.items():
            uid = (ids or {}).get(name) or new_id()
            self.ids[name] = uid
            self.headers[name] = auth(create_token(user_id=uid, organisation_id=self.id, roles=roles))

    def __getattr__(self, name: str) -> dict:
        try:
            return self.__dict__["headers"][name]
        except KeyError as e:
            raise AttributeError(name) from e

    def token(self, who: str) -> str:
        return self.headers[who]["Authorization"].split(" ", 1)[1]


def alumnus_body(**fields) -> dict:
    body = {
        "full_name": "Ananya Rao",
        "graduation_year": 2018,
        "programme": "MBA Finance",
        "current_company": "Axis Capital",
        "current_designation": "Associate Director",
        "industry": "Investment banking",
        "city": "Mumbai",
        "email": "ananya.rao@example.com",
        "phone": "+91 98450 12345",
        "linkedin_url": "https://www.linkedin.com/in/ananya-rao",
        "is_mentor": False,
        "notes": "STAFF-ONLY-NOTE about the alumnus",
    }
    body.update(fields)
    return body


def add_alumnus(client, org: Org, **fields) -> dict:
    r = client.post(f"{BASE}/directory", json=alumnus_body(**fields), headers=org.coord)
    assert r.status_code == 201, r.text
    return r.json()


def mentor(client, org: Org, **fields) -> dict:
    return add_alumnus(client, org, is_mentor=True, **fields)


def assign(client, org: Org, m: dict, student: str = "student", **fields):
    body = {"mentor_id": m["id"], "student_id": org.ids[student], "student_name": "Riya Sharma", **fields}
    return client.post(f"{BASE}/mentoring/assignments", json=body, headers=org.coord)


def assigned(client, org: Org, m: dict | None = None, student: str = "student", **fields) -> dict:
    r = assign(client, org, m or mentor(client, org), student, **fields)
    assert r.status_code == 201, r.text
    return r.json()


def session_body(at: datetime, **fields) -> dict:
    return {
        "scheduled_at": iso(at),
        "duration_minutes": 45,
        "mode": "online",
        "location": "https://meet.example.com/abc",
        "topic": "Careers in finance",
        **fields,
    }


def schedule(client, org: Org, x: dict, at: datetime, **fields):
    return client.post(
        f"{BASE}/mentoring/assignments/{x['id']}/sessions", json=session_body(at, **fields), headers=org.coord
    )


def scheduled(client, org: Org, x: dict, at: datetime, **fields) -> dict:
    r = schedule(client, org, x, at, **fields)
    assert r.status_code == 201, r.text
    return r.json()


def outbox(name: str, organisation_id: str) -> list[dict]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.name == name, OutboxEvent.organisation_id == organisation_id)
        return [e.payload for e in db.scalars(q.order_by(OutboxEvent.occurred_at))]


def code(r) -> str:
    return r.json()["detail"]["code"]
