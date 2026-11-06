"""Helpers shared by the digilocker tests (kept out of conftest.py so test files can import them)."""

import hashlib
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import parse_qs

import httpx
from eos_core.db import SessionLocal
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 5, 4, 30, 0, tzinfo=UTC)  # 10:00 IST: what the recorded fixtures were signed at
ISSUER_ID = "in.ac.example"
API_KEY = "issuer-api-key-fixture"
PUSH_ID, PUSH_SECRET = "PUSH-APP-001", "push-secret-fixture"
REDIRECT = "https://eos.example.com/api/v1/integration-hub/oauth/callback/digilocker"
PREFIX = "/api/v1/digilocker"


def fixed_clock() -> datetime:
    return NOW


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation with an org admin and a student, each with a platform token."""

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.admin = auth(create_token(user_id=str(uuid.uuid4()), organisation_id=self.id, roles=["org-admin"]))
        self.student = auth(create_token(user_id=str(uuid.uuid4()), organisation_id=self.id, roles=["student"]))

    def token(self, who: str) -> str:
        return getattr(self, who)["Authorization"].split(" ", 1)[1]


def fixture(name: str):
    path = FIXTURES / name
    return json.loads(path.read_text()) if name.endswith(".json") else path.read_bytes()


def settings(**overrides) -> dict:
    s = {
        "issuer_id": ISSUER_ID,
        "push_enabled": False,
        "doc_types": [
            {
                "doc_kind": "degree",
                "doc_type": "DGCER",
                "search_fields": ["roll_number", "year"],
                "send_pdf_on_uri_request": True,
                "has_xml": True,
            },
            {"doc_kind": "marksheet", "doc_type": "MKSHT", "search_fields": ["roll_number"]},
        ],
    }
    s.update(overrides)
    return s


def ctx(org: Org, *, mode="mock", secrets=None, link=None, **overrides) -> dict:
    c = {
        "organisation_id": org.id,
        "connection_id": str(uuid.uuid4()),
        "provider": "digilocker",
        "mode": mode,
        "settings": settings(),
        "secrets": {"issuer_api_key": API_KEY, "push_client_id": PUSH_ID, "push_client_secret": PUSH_SECRET}
        if secrets is None
        else secrets,
        "account_link": link,
        "delivery_id": str(uuid.uuid4()),
        "attempt": 1,
        "idempotency_key": "k",
    }
    c.update(overrides)
    return c


def link_ctx(org: Org, *, access="access-token-fixture", mode="mock", **overrides) -> dict:
    link = {"id": str(uuid.uuid4()), "person_id": str(uuid.uuid4()), "provider_subject": "dl-holder-0001"}
    return ctx(
        org,
        mode=mode,
        link=link,
        secrets={"access_token": access, "refresh_token": "refresh-token-fixture"},
        **overrides,
    )


def pdf(label: str = "degree") -> bytes:
    return f"%PDF-1.4 {label} fixture".encode()


def issue_input(
    documents, org: Org, *, number="DEG-2026-0001", key="res-1:degree", label="degree", **overrides
) -> dict:
    document_id, sha = documents.add(org.id, pdf(label))
    body = {
        "issuance_key": key,
        "doc_kind": "degree",
        "document_id": document_id,
        "document_sha256": sha,
        "document_number": number,
        "issued_on": "2026-11-05",
        "title": "B.Sc. Physics degree",
        "holder": {
            "person_id": str(uuid.uuid4()),
            "name": "Asha Rao",
            "date_of_birth": "2004-01-01",
            "gender": "F",
            "search_keys": {"roll_number": "RN-2026-0042", "year": 2026},
        },
        "data": {"cgpa": 8.4, "programme": "B.Sc. Physics"},
    }
    body.update(overrides)
    return body


def ok(result: dict) -> dict:
    assert "error" not in result, result
    return result["output"]


def err(result: dict) -> dict:
    assert "output" not in result, result
    return result["error"]


class Replay:
    """Replays recorded request/response pairs: every request must equal a recorded one (method, path, form and
    bearer token), so a change to the adapter's wire format fails here, with no network."""

    def __init__(self, *names: str):
        self.recorded = [fixture(n) for n in names]
        self.seen: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.seen.append(request)
        form = {k: v[0] for k, v in parse_qs(request.content.decode(), keep_blank_values=True).items()}
        for pair in self.recorded:
            rec = pair["request"]
            if rec["method"] != request.method or request.url.path != rec["path"]:
                continue
            if "form" in rec and rec["form"] != form:
                continue
            if "authorization" in rec and request.headers.get("authorization") != rec["authorization"]:
                continue
            res = pair["response"]
            if "content" in res:
                return httpx.Response(res["status"], content=res["content"].encode(), headers=res["headers"])
            return (
                httpx.Response(res["status"], json=res["body"])
                if res.get("body") is not None
                else httpx.Response(res["status"])
            )
        raise AssertionError(f"unrecorded request {request.method} {request.url.path} {form}")

    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self))


def rows(model, organisation_id: str | None = None) -> list:
    db = SessionLocal()
    try:
        with platform_scope():
            q = select(model)
            if organisation_id:
                q = q.where(model.organisation_id == organisation_id)
            return list(db.scalars(q))
    finally:
        db.close()


def sha(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()
