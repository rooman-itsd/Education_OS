"""Logs and errors (#91): one JSON `request` line per request with its request id and the organisation from a
verified token; every line written during the request carries both; nothing personal reaches the logs or Sentry."""

import io
import json
import logging

import jwt
import pytest
import structlog
from eos_backend.observability import REQUEST_ID, RequestContext, configure_logging, init_sentry, scrub
from eos_core.security import create_token
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route
from starlette.testclient import TestClient


@pytest.fixture
def lines():
    """The JSON lines logged while the test runs."""
    buf = io.StringIO()
    configure_logging(fmt="json", level="INFO", stream=buf)
    yield lambda: [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    configure_logging(fmt="json", level="INFO")


def _request_line(records: list[dict], path: str) -> dict:
    (line,) = [r for r in records if r.get("event") == "request" and r.get("path") == path]
    return line


def test_one_request_line_with_the_verified_organisation(client, lines):
    a = register_and_login(client, slug="obs-me")
    r = client.get("/api/v1/identity/auth/me", headers=auth(a["token"]))
    assert r.status_code == 200
    line = _request_line(lines(), "/api/v1/identity/auth/me")
    assert line["organisation_id"] == a["org"]["id"]
    assert line["status"] == 200 and line["method"] == "GET"
    assert line["module"] == "identity" and line["route"] == "/auth/me" and isinstance(line["duration_ms"], float)
    assert line["request_id"] == r.headers[REQUEST_ID] and line["level"] == "info" and "timestamp" in line


def test_the_token_and_the_password_never_reach_the_logs(client, lines):
    a = register_and_login(client, slug="obs-secret")
    client.get("/api/v1/identity/auth/me?email=someone@example.com", headers=auth(a["token"]))
    text = json.dumps(lines())
    assert a["token"] not in text and "Passw0rd" not in text
    assert "someone@example.com" not in text  # the query string is not logged


def test_a_forged_token_logs_no_organisation(client, lines):
    forged = jwt.encode({"sub": "x", "org": "forged-org"}, "not-the-secret-" * 4, algorithm="HS256")
    client.get("/api/v1/identity/auth/me", headers=auth(forged))
    line = _request_line(lines(), "/api/v1/identity/auth/me")
    assert line["organisation_id"] is None and line["status"] == 401


def test_an_anonymous_request_has_no_organisation(client, lines):
    client.get("/api/v1/health")
    assert _request_line(lines(), "/api/v1/health")["organisation_id"] is None


def test_a_plain_request_id_is_kept_and_anything_else_replaced(client, lines):
    kept = client.get("/api/v1/health", headers={REQUEST_ID: "support-ticket-42"})
    assert kept.headers[REQUEST_ID] == "support-ticket-42"
    replaced = client.get("/api/v1/health", headers={REQUEST_ID: "bad id with spaces"})
    assert replaced.headers[REQUEST_ID] != "bad id with spaces" and len(replaced.headers[REQUEST_ID]) == 32
    assert {r["request_id"] for r in lines() if r.get("event") == "request"} >= {"support-ticket-42"}


def test_every_line_during_the_request_carries_both_ids(lines):
    """A module's own log line, written inside the request, gets the ids without passing them around."""

    def handler(request):
        logging.getLogger("eos.somemodule").info("did a thing")
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/x", handler)])
    app.add_middleware(RequestContext)
    token = create_token(user_id="u1", organisation_id="org-1", roles=["student"])
    with TestClient(app) as c:
        c.get("/x", headers={"Authorization": f"Bearer {token}", REQUEST_ID: "req-1"})
    (inner,) = [r for r in lines() if r.get("event") == "did a thing"]
    assert inner["organisation_id"] == "org-1" and inner["request_id"] == "req-1"
    assert inner["logger"] == "eos.somemodule"


def test_sentry_gets_the_ids_and_nothing_personal():
    structlog.contextvars.bind_contextvars(organisation_id="org-9", request_id="req-9")
    try:
        event = scrub(
            {
                "request": {
                    "url": "https://api/x",
                    "data": {"password": "p"},
                    "cookies": {"s": "1"},
                    "query_string": "email=a@b.c",
                    "headers": {"Authorization": "Bearer t", "User-Agent": "ua", "X-Forwarded-For": "1.2.3.4"},
                },
                "user": {"email": "a@b.c", "ip_address": "1.2.3.4"},
            }
        )
    finally:
        structlog.contextvars.clear_contextvars()
    assert set(event["request"]) == {"url", "headers"} and event["request"]["headers"] == {"User-Agent": "ua"}
    assert "user" not in event
    assert event["tags"] == {"organisation_id": "org-9", "request_id": "req-9"}


def test_sentry_stays_off_without_a_dsn(monkeypatch):
    monkeypatch.delenv("EOS_SENTRY_DSN", raising=False)
    assert init_sentry() is False
