"""Helpers shared by the placement-career tests (kept out of conftest.py so test files can import them)."""

from __future__ import annotations

import itertools
from datetime import UTC, date, datetime, timedelta

import jwt
from eos_core.db import SessionLocal, new_id
from eos_core.events import OutboxEvent
from eos_core.settings import settings
from eos_core.tenant import platform_scope
from sqlalchemy import select

BASE = "/api/v1/placement-career"
NOW = datetime(2026, 11, 3, 6, 0, tzinfo=UTC)  # 11:30 on 3 November in Asia/Kolkata
TODAY = date(2026, 11, 3)
_names = itertools.count(1)


def day(offset: int) -> str:
    """An Indian business date relative to TODAY, as the API takes it."""
    return (TODAY + timedelta(days=offset)).isoformat()


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def token(user_id: str, organisation_id: str, roles: list[str], name: str | None = None) -> str:
    """A token as identity issues it, with a `name` claim when given."""
    now = datetime.now(UTC)
    claims = {
        "sub": user_id,
        "org": organisation_id,
        "roles": roles,
        "sa": False,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    if name is not None:
        claims["name"] = name
    return jwt.encode(claims, settings.jwt_secret, algorithm="HS256")


class Clock:
    """The service's clock, moved by tests. Each reading is a millisecond after the one before, so rows created one
    after another keep their order ("newest first") as they would in real time."""

    def __init__(self):
        self.now = NOW

    def __call__(self) -> datetime:
        self.now = self.now + timedelta(milliseconds=1)
        return self.now

    def advance(self, **delta) -> None:
        self.now = self.now + timedelta(**delta)


class Org:
    """An organisation with one user per role. The officer, coordinator and liaison roles are dashboard layouts that
    hold placement-career-officer or -viewer through module_roles; the management student extends `student`."""

    ROLES = {
        "officer": ["placement-officer"],
        "coordinator": ["industry-coordinator"],
        "viewer": ["industry-liaison"],
        "student": ["student"],
        "student2": ["management-student"],
        "student3": ["student"],
        "nobody": [],
    }
    NAMES = {"student": "Asha Rao", "student2": "Kiran Shetty"}

    def __init__(self):
        self.id = new_id()
        self.ids: dict[str, str] = {}
        self.headers: dict[str, dict] = {}
        for who, roles in self.ROLES.items():
            uid = new_id()
            self.ids[who] = uid
            self.headers[who] = auth(token(uid, self.id, roles, self.NAMES.get(who)))

    def __getattr__(self, name: str) -> dict:
        try:
            return self.__dict__["headers"][name]
        except KeyError as e:
            raise AttributeError(name) from e

    def token(self, who: str) -> str:
        return self.headers[who]["Authorization"].split(" ", 1)[1]


def ok(r, status: int = 200) -> dict:
    assert r.status_code == status, r.text
    return r.json()


def code(r, status: int) -> str:
    assert r.status_code == status, r.text
    return r.json()["detail"]["code"]


def company(client, org: Org, **fields) -> dict:
    body = {
        "name": f"Acme Systems {next(_names)}",
        "industry": "IT services",
        "website": "https://acme.example",
        **fields,
    }
    return ok(client.post(f"{BASE}/companies", json=body, headers=org.officer), 201)


def drive(client, org: Org, co: dict | None = None, *, schedule: bool = True, **fields) -> dict:
    co = co or company(client, org)
    body = {
        "company_id": co["id"],
        "title": "Campus drive",
        "scheduled_on": day(10),
        "venue": "Main auditorium",
        "registration_closes_on": day(7),
        "rounds": ["Aptitude test", "Technical interview", "HR interview"],
        "eligibility": {"programmes": ["B.Tech"], "graduating_years": [2027], "min_cgpa": 6.5},
        **fields,
    }
    d = ok(client.post(f"{BASE}/drives", json=body, headers=org.officer), 201)
    if schedule:
        d = ok(client.post(f"{BASE}/drives/{d['id']}/schedule", headers=org.officer))
    return d


def opening(client, org: Org, *, co: dict | None = None, dr: dict | None = None, publish: bool = True, **fields):
    if co is None:
        co = {"id": dr["company_id"]} if dr else company(client, org)
    body = {
        "company_id": co["id"],
        "drive_id": dr["id"] if dr else None,
        "title": "Graduate engineer trainee",
        "location": "Bengaluru",
        "ctc_per_annum": "650000.00",
        "positions": 5,
        "applications_close_on": day(5),
        "eligibility": {"min_cgpa": 7, "max_active_backlogs": 0},
        **fields,
    }
    o = ok(client.post(f"{BASE}/openings", json=body, headers=org.officer), 201)
    if publish:
        o = ok(client.post(f"{BASE}/openings/{o['id']}/publish", headers=org.officer))
    return o


def apply(client, org: Org, o: dict, who: str = "student", **fields):
    body = {"opening_id": o["id"], "declares_eligible": True, **fields}
    return client.post(f"{BASE}/me/applications", json=body, headers=org.headers[who])


def applied(client, org: Org, o: dict | None = None, who: str = "student", **fields) -> dict:
    o = o or opening(client, org)
    return ok(apply(client, org, o, who, **fields), 201)


def move(client, org: Org, a: dict, status: str, who: str = "officer", **fields):
    return client.post(
        f"{BASE}/applications/{a['id']}/status", json={"status": status, **fields}, headers=org.headers[who]
    )


def outbox(organisation_id: str, name: str | None = None) -> list[OutboxEvent]:
    with SessionLocal() as db, platform_scope():
        q = select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)
        if name:
            q = q.where(OutboxEvent.name == name)
        return list(db.scalars(q.order_by(OutboxEvent.occurred_at)))
