"""Helpers shared by the wearables tests (kept out of conftest.py so test files can import them by a unique name)."""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
from eos_core.db import new_id
from eos_core.security import create_token

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 5, 6, 0, tzinfo=UTC)
PREFIX = "/api/v1/wearables"
POLAR_KEY = "polar-signature-secret-key"
STRAVA_VERIFY = "strava-verify-token"
STRAVA_SUB = "120475"
STRAVA_ATHLETE = "12345678"
GARMIN_USER = "d3b1c9a2-7f4e-4b8a-9c11-0a5e6f7d8e90"


def fixture(path: str) -> str:
    return (FIXTURES / path).read_text()


def fixture_json(path: str):
    return json.loads(fixture(path))


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Clock:
    def __init__(self, now: datetime = NOW):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **delta) -> None:
        self.now += timedelta(**delta)


class Transport:
    """The only 'network' a test sees: routes are (method, URL regex) -> a response, answered in order when several are given.
    A request nothing routes is a test failure, so no call goes to a provider that the test did not expect."""

    def __init__(self):
        self.routes: list[tuple[str, re.Pattern, list]] = []
        self.requests: list[httpx.Request] = []
        self.unexpected: list[str] = []  # the adapter turns an exception into a Result, so the fixture checks this too

    def on(
        self,
        method: str,
        url: str,
        *answers,
        status: int = 200,
        body=None,
        headers: dict | None = None,
        raises: Exception | None = None,
    ):
        queue = list(answers) or [(status, body, headers or {}, raises)]
        norm = [(status, fixture(a), headers or {}, raises) if isinstance(a, str) else a for a in queue]
        self.routes.append((method.upper(), re.compile(url), norm))
        return self

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        for method, pattern, answers in self.routes:
            if method == request.method and pattern.search(str(request.url)):
                status, body, headers, raises = answers[0] if len(answers) == 1 else answers.pop(0)
                if raises:
                    raise raises
                if isinstance(body, (dict, list)):
                    body = json.dumps(body)
                if isinstance(body, str):
                    body = body.encode()
                return httpx.Response(status, content=body or b"", headers=headers, request=request)
        self.unexpected.append(f"{request.method} {request.url}")
        raise AssertionError(f"unexpected request: {request.method} {request.url}")

    def factory(self):
        return lambda: httpx.Client(transport=httpx.MockTransport(self))

    def sent(self, method: str, url: str) -> list[httpx.Request]:
        return [r for r in self.requests if r.method == method and re.search(url, str(r.url))]

    def last(self, method: str, url: str) -> httpx.Request:
        return self.sent(method, url)[-1]


def body_of(request: httpx.Request) -> dict:
    return json.loads(request.content)


def form_of(request: httpx.Request) -> dict:
    from urllib.parse import parse_qsl

    return dict(parse_qsl(request.content.decode()))


SETTINGS = {
    "garmin": lambda: {"garmin_tier": "starter"},
    "polar": lambda: {},
    "google-health": lambda: {},
    "strava": lambda: {},
}
SECRETS = {
    "garmin": lambda: {"access_token": "garmin-access-1", "refresh_token": "garmin-refresh-1"},
    "polar": lambda: {"access_token": "polar-access-1"},
    "google-health": lambda: {"access_token": "google-access-1", "refresh_token": "google-refresh-1"},
    "strava": lambda: {"access_token": "strava-access-1", "refresh_token": "strava-refresh-1"},
}
SUBJECTS = {"garmin": GARMIN_USER, "polar": "475", "google-health": "10987654321", "strava": STRAVA_ATHLETE}


class Org:
    """An organisation with a connection per provider, athletes, and a user per role for the alerts API."""

    def __init__(self):
        self.id = new_id()
        self.connection_id = new_id()
        self.coach = auth(create_token(user_id=new_id(), organisation_id=self.id, roles=["coach"]))
        self.admin = auth(create_token(user_id=new_id(), organisation_id=self.id, roles=["org-admin"]))
        self.faculty = auth(create_token(user_id=new_id(), organisation_id=self.id, roles=["faculty"]))
        self.athlete_token = auth(create_token(user_id=new_id(), organisation_id=self.id, roles=["athlete"]))

    def ctx(self, provider: str, person: str | None = None, link: str | None = None, **over) -> dict:
        base = {
            "organisation_id": self.id,
            "connection_id": self.connection_id,
            "provider": provider,
            "mode": "sandbox",
            "settings": SETTINGS[provider](),
            "secrets": SECRETS[provider](),
            "delivery_id": str(uuid.uuid4()),
        }
        if link:
            base["account_link"] = {"id": link, "person_id": person, "provider_subject": SUBJECTS[provider]}
        base.update(over)
        return base


def link_input(person: str, provider: str, **over) -> dict:
    base = {
        "person_id": person,
        "provider": provider,
        "data_types": [],
        "state": "state-123",
        "code_challenge": "C" * 43,
        "redirect_uri": "https://hub.example/cb",
    }
    base.update(over)
    return base


def polar_signature(raw: bytes, key: str = POLAR_KEY) -> dict:
    return {"Polar-Webhook-Signature": hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()}


def request(raw: bytes | str, headers: dict | None = None, *, method="POST", query=None, suffix="") -> dict:
    return {
        "method": method,
        "path_suffix": suffix,
        "query": query or {},
        "headers": headers or {},
        "raw_body": raw.encode() if isinstance(raw, str) else raw,
    }


def new_ids():
    return str(uuid.uuid4()), str(uuid.uuid4())


_ = hashlib


def make_link(
    org: Org,
    provider: str,
    person: str | None = None,
    *,
    status="active",
    subject: str | None = None,
    types=None,
    **fields,
) -> dict:
    """An account link as the hub would have made it, inserted directly (the linking flow has its own tests)."""
    from eos_core.db import SessionLocal
    from eos_wearables.infrastructure.models import LinkState

    person = person or str(uuid.uuid4())
    link = str(uuid.uuid4())
    row = LinkState(
        organisation_id=org.id, connection_id=org.connection_id, account_link_id=link, person_id=person, provider=provider,
        provider_subject=subject or SUBJECTS[provider], status=status, status_since=NOW - timedelta(days=1), created_at=NOW - timedelta(days=1),
        data_types=types if types is not None else {"strava": ["activity"], "polar": ["daily_summary", "activity", "sleep"]}.get(provider, ["daily_summary", "activity", "sleep", "heart_rate_variability", "body_composition"]),
    )  # fmt: skip
    for k, v in fields.items():
        setattr(row, k, v)
    with SessionLocal() as db:
        db.add(row)
        db.commit()
    return {"link": link, "person": person}


def link_row(link: str):
    from eos_core.db import SessionLocal
    from eos_core.tenant import platform_scope
    from eos_wearables.infrastructure.models import LinkState
    from sqlalchemy import select

    with platform_scope(), SessionLocal() as db:
        row = db.scalar(select(LinkState).where(LinkState.account_link_id == link))
        db.expunge(row)
        return row


def records(link: str | None = None, org: Org | None = None) -> list:
    from eos_core.db import SessionLocal
    from eos_core.tenant import platform_scope
    from eos_wearables.infrastructure.models import Record
    from sqlalchemy import select

    q = select(Record)
    if link:
        q = q.where(Record.account_link_id == link)
    if org:
        q = q.where(Record.organisation_id == org.id)
    with platform_scope(), SessionLocal() as db:
        rows = db.scalars(q).all()
        for r in rows:
            db.expunge(r)
        return rows


def audit_actions(org: Org) -> list[str]:
    from eos_core.db import SessionLocal
    from eos_core.tenant import platform_scope
    from eos_wearables.infrastructure.models import AuditEntry
    from sqlalchemy import select

    with platform_scope(), SessionLocal() as db:
        return [
            a.action
            for a in db.scalars(
                select(AuditEntry)
                .where(AuditEntry.organisation_id == org.id)
                .order_by(AuditEntry.occurred_at, AuditEntry.id)
            )
        ]
