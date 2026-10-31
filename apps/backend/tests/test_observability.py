"""Logs and errors (#91): one JSON `request` line per request with its request id and the organisation from a
verified token; every line written during the request carries both; nothing personal reaches the logs or Sentry."""

import io
import json
import logging

import jwt
import pytest
import sentry_sdk
import structlog
from eos_backend.observability import REQUEST_ID, RequestContext, configure_logging, init_sentry, scrub
from eos_core.security import create_token
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from sentry_sdk.transport import Transport
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


class _Capture(Transport):
    """Keeps the events Sentry would send, in this process."""

    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict] = []

    def capture_envelope(self, envelope):
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)


def test_a_password_in_local_variables_or_an_email_in_the_message_never_reaches_sentry(monkeypatch):
    """An exception inside, say, tenancy.register() has the admin's password and email in its locals."""
    monkeypatch.setenv("EOS_SENTRY_DSN", "https://public@sentry.example.invalid/1")
    transport = _Capture()
    assert init_sentry(transport=transport) is True
    try:

        def register(admin_email: str):
            password = "Local-Passw0rd!"  # noqa: F841 (a local variable is the point)
            raise ValueError(f"{admin_email} is already registered")

        try:
            register("someone@example.com")
        except ValueError:
            sentry_sdk.capture_exception()
        logging.getLogger("eos.tenancy").error("could not mail %s", "other@example.com")
        sentry_sdk.flush()
    finally:
        sentry_sdk.init()  # no DSN: off again for the other tests
    text = json.dumps(transport.events, default=str)
    assert transport.events, "Sentry captured nothing"
    assert "Local-Passw0rd!" not in text
    assert "someone@example.com" not in text and "other@example.com" not in text
    assert "[email] is already registered" in text


def test_a_mistyped_log_level_falls_back_to_info_and_says_so():
    buf = io.StringIO()
    try:
        configure_logging(fmt="json", level="LOUD", stream=buf)
        logging.getLogger("eos.x").info("still logging")
    finally:
        configure_logging(fmt="json", level="INFO")
    records = [json.loads(line) for line in buf.getvalue().splitlines() if line.strip()]
    assert any("EOS_LOG_LEVEL=LOUD" in r["event"] and r["level"] == "warning" for r in records)
    assert any(r["event"] == "still logging" for r in records)


def test_an_unhandled_error_is_logged_with_both_ids(lines):
    def handler(request):
        raise RuntimeError("boom")

    app = Starlette(routes=[Route("/x", handler)])
    app.add_middleware(RequestContext)
    token = create_token(user_id="u1", organisation_id="org-1", roles=["student"])
    with TestClient(app, raise_server_exceptions=False) as c:
        r = c.get("/x", headers={"Authorization": f"Bearer {token}", REQUEST_ID: "req-err"})
    assert r.status_code == 500
    (err,) = [x for x in lines() if x.get("event") == "unhandled error"]
    assert err["request_id"] == "req-err" and err["organisation_id"] == "org-1"
    assert err["level"] == "error" and "RuntimeError: boom" in err["exception"]
    assert _request_line(lines(), "/x")["status"] == 500


def test_the_gate_puts_its_verified_organisation_on_the_modules_lines(lines, monkeypatch):
    """A Keycloak token: RequestContext does not verify it, the gate does, and the module's lines carry the org."""
    import eos_backend.gateway as gateway
    import eos_backend.observability as observability
    from eos_tenancy.application import service as tenancy

    monkeypatch.setattr(observability, "_verified_organisation", lambda request: None)
    monkeypatch.setattr(gateway, "decode_token", lambda token: {"org": "org-kc"})
    monkeypatch.setattr(gateway, "SessionLocal", lambda: type("Db", (), {"close": lambda self: None})())
    monkeypatch.setattr(tenancy, "entitlement", lambda db, org: {"status": "active"})
    monkeypatch.setattr(gateway, "module_entitled", lambda ent, module: True)

    def handler(request):
        logging.getLogger("eos.somemodule").info("module line")
        return JSONResponse({"ok": True})

    app = Starlette(routes=[Route("/api/v1/somemodule/x", handler)])
    app.add_middleware(gateway.EntitlementGate)
    app.add_middleware(RequestContext)
    with TestClient(app) as c:
        assert c.get("/api/v1/somemodule/x", headers={"Authorization": "Bearer kc-token"}).status_code == 200
    (inner,) = [r for r in lines() if r.get("event") == "module line"]
    assert inner["organisation_id"] == "org-kc"
    assert _request_line(lines(), "/api/v1/somemodule/x")["organisation_id"] == "org-kc"
