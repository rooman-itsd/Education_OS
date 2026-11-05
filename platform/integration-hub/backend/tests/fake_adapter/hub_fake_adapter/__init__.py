"""A tiny adapter for the hub's own tests. NOT a provider, never installed: conftest.py puts this folder on sys.path,
and the `hub_fake_adapter-0.1.0.dist-info` beside it registers it on the real `eos.integration_adapters` entry-point
group, so the hub finds it exactly as it finds a real adapter.

It follows contracts/ports/adapter.yaml with three providers, answers port operations from the recorded fixtures in
tests/fixtures (no network), verifies callbacks with an HMAC-SHA256 over the raw body, and answers handshakes the way
Zoom (endpoint.url_validation) and Strava (hub.challenge) do. Tests steer it through SCRIPT and STATE."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
from pathlib import Path

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures"

# operation -> results to hand out first (one per call), then the fixture or the default answer.
SCRIPT: dict[str, list] = {}
# What the adapter saw: (operation, mode, sorted secret names, port). Never a secret value.
CALLS: list[tuple] = []
STATE: dict = {}

APP_KEY_ENV = "FAKE_ADAPTER_APP_KEY"
VERIFY_TOKEN_ENV = "FAKE_ADAPTER_VERIFY_TOKEN"


def reset() -> None:
    SCRIPT.clear()
    CALLS.clear()
    STATE.clear()
    STATE.update({"health": "healthy", "challenges": {}, "revoked": [], "refresh": "ok"})


reset()


def sign(secret: str, raw: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()


def _fixture(name: str) -> dict:
    return json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))


def _get(ctx, key):
    return ctx[key] if not hasattr(ctx, key) else getattr(ctx, key)


def _record(op: str, ctx) -> None:
    CALLS.append((op, _get(ctx, "mode"), tuple(sorted(_get(ctx, "secrets") or {})), _get(ctx, "port")))


def _scripted(op: str):
    queue = SCRIPT.get(op)
    if queue:
        result = queue.pop(0)
        if isinstance(result, Exception):
            raise result
        return result
    return None


SETTINGS = {
    "type": "object",
    "properties": {
        "account_id": {"type": "string", "maxLength": 40},
        "region": {"type": "string", "enum": ["in", "us"]},
    },
    "additionalProperties": False,
}


class FakeAdapter:
    def describe(self) -> dict:
        return {
            "adapter": "fake-adapter",
            "version": "0.1.0",
            "ports": [
                {"port": "meetings", "version": 1},
                {"port": "wearable-data", "version": 1},
                {"port": "certificate-issuance", "version": 1},
            ],
            "providers": [
                {
                    "provider": "fakemeet",
                    "title": "Fake Meet",
                    "ports": ["meetings"],
                    "modes": ["mock", "sandbox", "live"],
                    "auth": "oauth2_authorization_code",
                    "link_scope": "organisation",
                    "inbound": ["webhook"],
                    "settings_schema": SETTINGS,
                    "credential_names": ["client_id", "client_secret"],
                    "platform_credential_names": [APP_KEY_ENV],
                },
                {
                    "provider": "fakewear",
                    "title": "Fake Wear",
                    "ports": ["wearable-data"],
                    "modes": ["mock", "sandbox"],
                    "auth": "oauth2_authorization_code",
                    "link_scope": "person",
                    "inbound": ["webhook"],
                    "settings_schema": {},
                    "credential_names": [],
                    "platform_credential_names": ["client_secret"],
                },
                {
                    "provider": "fakecert",
                    "title": "Fake Cert",
                    "ports": ["certificate-issuance"],
                    "modes": ["mock", "sandbox", "live"],
                    "auth": "hmac_shared_secret",
                    "link_scope": "organisation",
                    "inbound": ["webhook", "provider_request"],
                    "settings_schema": {},
                    "credential_names": ["api_key", "webhook_secret"],
                    "platform_credential_names": [],
                },
            ],
        }

    # --- adapter.yaml ----------------------------------------------------------------------------------------

    def capabilities(self, ctx, payload):
        return {"output": {"port": _get(ctx, "port"), "capabilities": {}}}

    def healthcheck(self, ctx):
        _record("healthcheck", ctx)
        scripted = _scripted("healthcheck")
        if scripted is not None:
            return scripted
        if (_get(ctx, "secrets") or {}).get("client_secret") == "wrong":
            return {"error": {"code": "auth_failed", "detail": "the provider refused the client secret"}}
        return {"output": {"status": STATE["health"], "detail": "ok", "expires_at": None}}

    def begin_authorisation(self, ctx, payload):
        _record("begin_authorisation", ctx)
        STATE["challenges"][payload["state"]] = payload["code_challenge"]
        STATE["last_state"] = payload["state"]
        STATE["redirect_uri"] = payload["redirect_uri"]
        return {"output": {"authorize_url": f"https://auth.fake.example/authorize?state={payload['state']}"}}

    def complete_authorisation(self, ctx, payload):
        _record("complete_authorisation", ctx)
        scripted = _scripted("complete_authorisation")
        if scripted is not None:
            return scripted
        verifier = payload["code_verifier"].encode()
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier).digest()).rstrip(b"=").decode()
        if challenge not in STATE["challenges"].values() or payload["code"] != "good-code":
            return {"error": {"code": "auth_failed", "detail": "code or verifier refused"}}
        return {
            "output": {
                "secrets": {"access_token": "at-" + payload["code"], "refresh_token": "rt-secret-value"},
                "provider_subject": STATE.get("subject", "fake-user-1"),
                "granted_scopes": ["activity", "sleep"],
                "expires_at": "2026-11-05T13:00:00+00:00",
            }
        }

    def refresh_authorisation(self, ctx):
        _record("refresh_authorisation", ctx)
        if STATE["refresh"] != "ok":
            return {"error": {"code": "auth_failed"}}
        return {"output": {"secrets": {"access_token": "at-refreshed"}, "expires_at": "2026-11-06T13:00:00+00:00"}}

    def revoke_authorisation(self, ctx):
        _record("revoke_authorisation", ctx)
        STATE["revoked"].append((_get(ctx, "account_link") or {}).get("id"))
        return {"output": {"revoked": True}}

    def verify_inbound(self, ctx, req):
        raw: bytes = req["raw_body"]
        headers = req["headers"]
        query = req["query"]
        if req["method"] == "GET":
            # Strava-style subscription check
            if query.get("hub.mode") == "subscribe" and query.get("hub.verify_token") == os.environ.get(
                VERIFY_TOKEN_ENV
            ):
                return {
                    "verdict": "handshake",
                    "handshake_response": {"status": 200, "body": {"hub.challenge": query.get("hub.challenge")}},
                }
            return {"verdict": "reject", "reject_status": 404}
        connection_level = _get(ctx, "connection_id") is not None
        secrets = _get(ctx, "secrets") or {}
        secret = (
            (secrets.get("webhook_secret") or secrets.get("client_secret"))
            if connection_level
            else os.environ.get(APP_KEY_ENV)
        )
        if not secret:
            return {"verdict": "reject"}
        given = headers.get("x-fake-signature", "")
        if not hmac.compare_digest(given, sign(secret, raw)):
            return {"verdict": "reject"}
        body = json.loads(raw or b"{}") if "json" in headers.get("content-type", "") else {}
        if body.get("event") == "endpoint.url_validation":
            plain = body["payload"]["plainToken"]
            encrypted = hmac.new(secret.encode(), plain.encode(), hashlib.sha256).hexdigest()
            return {
                "verdict": "handshake",
                "handshake_response": {"status": 200, "body": {"plainToken": plain, "encryptedToken": encrypted}},
            }
        out = {"verdict": "accept", "dedupe_key": body.get("event_id")}
        if not connection_level:
            out["resolves_to"] = {"account_link_subject": body.get("owner_id")}
        if body.get("ack") in (202, 204):
            out["ack_status"] = body["ack"]
        return out

    def parse_inbound(self, ctx, req):
        _record("parse_inbound", ctx)
        scripted = _scripted("parse_inbound")
        if scripted is not None:
            return scripted
        body = json.loads(req["raw_body"] or b"{}")
        event, data = body.get("event"), body.get("payload") or {}
        kinds = {
            "meeting.started": ("meetings", "meeting_started"),
            "meeting.ended": ("meetings", "meeting_ended"),
            "meeting.participant_joined": ("meetings", "participant_joined"),
            "attendance.ready": ("meetings", "attendance_ready"),
            "recording.completed": ("meetings", "recording_ready"),
            "activity": ("wearable-data", "data_available"),
            "deauthorize": ("wearable-data", "link_revoked_by_provider"),
            "document.pulled": ("certificate-issuance", "document_pulled"),
        }
        if event not in kinds:
            return {"output": {"notifications": []}}
        port, kind = kinds[event]
        if port == "wearable-data":
            data = {**data, "account_link_subject": body.get("owner_id")}
        return {"output": {"notifications": [{"port": port, "kind": kind, "data": data}]}}

    def handle_provider_request(self, ctx, req):
        _record("handle_provider_request", ctx)
        if req["channel"] != "pull-uri":
            return {"error": {"code": "not_found"}}
        return {
            "output": {
                "status": 200,
                "content_type": "application/xml",
                "body": '<?xml version="1.0"?><PullURIResponse><Status>1</Status></PullURIResponse>',
            }
        }

    # --- port operations, from recorded fixtures --------------------------------------------------------------

    def _port_call(self, op: str, ctx, payload, fixture: str | None):
        _record(op, ctx)
        scripted = _scripted(op)
        if scripted is not None:
            return scripted
        if fixture:
            return _fixture(fixture)
        return {"output": {}}

    def create_meeting(self, ctx, payload):
        return self._port_call("create_meeting", ctx, payload, "meetings_create_meeting")

    def fetch_attendance(self, ctx, payload):
        return self._port_call("fetch_attendance", ctx, payload, "meetings_fetch_attendance")

    def issue(self, ctx, payload):
        return self._port_call("issue", ctx, payload, "certificate_issue")

    def withdraw(self, ctx, payload):
        out = self._port_call("withdraw", ctx, payload, None)
        return out if out.get("output") or out.get("error") else {"output": {"status": "withdrawn"}}

    def sync(self, ctx, payload):
        out = self._port_call("sync", ctx, payload, None)
        if out.get("output") or out.get("error"):
            return out
        return {"output": {"stored": 3, "updated": 0, "from": payload.get("from"), "to": payload.get("to")}}
