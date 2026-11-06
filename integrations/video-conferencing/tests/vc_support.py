"""Helpers shared by the video-conferencing tests (kept out of conftest.py so test files can import them by a unique name)."""

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
START = "2026-11-09T04:30:00+00:00"  # 10:00 on 9 November in Asia/Kolkata
PREFIX = "/api/v1/video-conferencing"
ZOOM_SECRET = "zoom-webhook-secret-token"
WEBEX_SECRET = "webex-webhook-secret"
DATA_KEY = "dmlkZW8tY29uZmVyZW5jaW5nLXRlc3Qta2V5LTAwMDE="  # a Fernet key made for these tests, protects nothing
JITSI_SECRET = "jitsi-app-secret-0123456789abcdef"


def fixture(path: str) -> str:
    return (FIXTURES / path).read_text()


def fixture_json(path: str) -> dict:
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
    """The only 'network' a test sees: routes are (method, URL regex) -> a response, answered in order when a list is given.
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
        """on("POST", r"api.zoom.us/v2/users/.*/meetings", "zoom/create_meeting.json") or status=204, or raises=httpx.ConnectTimeout(...)"""
        queue = list(answers) or [(status, body, headers or {}, raises)]
        norm = []
        for a in queue:
            if isinstance(a, str):
                norm.append((status, fixture(a), headers or {}, raises))
            elif isinstance(a, tuple):
                norm.append(a)
            else:
                norm.append(a)
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


class Documents:
    """platform/documents stand-in: consumes the chunks and remembers them."""

    def __init__(self):
        self.stored: list[dict] = []

    def store(self, *, organisation_id, name, content_type, chunks):
        data = b"".join(chunks)
        doc = str(uuid.uuid4())
        self.stored.append(
            {"id": doc, "organisation_id": organisation_id, "name": name, "content_type": content_type, "data": data}
        )
        return doc


class Org:
    """An organisation with its connections per provider, and users per role for the operator API."""

    def __init__(self, provider: str = "zoom", **over):
        self.id = new_id()
        self.connection_id = new_id()
        self.provider = provider
        self.over = over
        self.admin = auth(create_token(user_id=new_id(), organisation_id=self.id, roles=["org-admin"]))
        self.faculty = auth(create_token(user_id=new_id(), organisation_id=self.id, roles=["faculty"]))

    def ctx(self, provider: str | None = None, **over) -> dict:
        provider = provider or self.provider
        base = {
            "organisation_id": self.id,
            "connection_id": self.connection_id,
            "provider": provider,
            "mode": "sandbox",
            "settings": SETTINGS[provider](),
            "secrets": SECRETS[provider](),
            "delivery_id": str(uuid.uuid4()),
        }
        base.update(self.over)
        base.update(over)
        return base


SETTINGS = {
    "zoom": lambda: {"account_id": "acct-1"},
    "teams": lambda: {"tenant_id": "11111111-2222-3333-4444-555555555555"},
    "webex": lambda: {"site_url": "college.webex.example"},
    "jitsi": lambda: {"base_url": "https://meet.college.example", "app_id": "eos-college"},
}
SECRETS = {
    "zoom": lambda: {"client_id": "s2s-id", "client_secret": "s2s-secret"},
    "teams": lambda: {},
    "webex": lambda: {"access_token": "webex-access-1", "webhook_secret": WEBEX_SECRET},
    "jitsi": lambda: {"app_secret": JITSI_SECRET},
}


def create_input(key: str = "class-session-1", **over) -> dict:
    base = {
        "meeting_key": key,
        "title": "Physics XI A: Optics",
        "starts_at": START,
        "duration_minutes": 45,
        "timezone": "Asia/Kolkata",
        "host": {"person_id": str(uuid.uuid4()), "email": "teacher@college.example.com"},
        "co_hosts": [],
        "options": {
            "waiting_room": True,
            "record": "cloud",
            "join_before_host": False,
            "authenticated_join_only": False,
        },
    }
    base.update(over)
    return base


def zoom_signature(body: bytes, ts: int | str, secret: str = ZOOM_SECRET) -> dict:
    sig = "v0=" + hmac.new(secret.encode(), f"v0:{ts}:".encode() + body, hashlib.sha256).hexdigest()
    return {"x-zm-signature": sig, "x-zm-request-timestamp": str(ts)}


def request(raw: bytes | str, headers: dict | None = None, *, method="POST", suffix="", query=None) -> dict:
    return {
        "method": method,
        "path_suffix": suffix,
        "query": query or {},
        "headers": headers or {},
        "raw_body": raw.encode() if isinstance(raw, str) else raw,
    }
