"""Helpers shared by the government-portals tests."""

import copy
import json
import uuid
from pathlib import Path

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from eos_government_portals.domain.port import Context
from sqlalchemy import select

PREFIX = "/api/v1/government-portals"
GOLDEN = Path(__file__).resolve().parent / "golden"
CASES = sorted(p.name for p in GOLDEN.iterdir() if (p / "input.json").is_file())


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


class Org:
    """An organisation with an org admin and a student, each with a platform token."""

    def __init__(self):
        self.id = str(uuid.uuid4())
        self.admin_id, self.student_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.admin = auth(create_token(user_id=self.admin_id, organisation_id=self.id, roles=["org-admin"]))
        self.student = auth(create_token(user_id=self.student_id, organisation_id=self.id, roles=["student"]))

    def token(self, who: str) -> str:
        return getattr(self, who)["Authorization"].split(" ", 1)[1]

    def ctx(self, provider: str, mode: str = "mock", **kw) -> Context:
        return Context(organisation_id=self.id, provider=provider, mode=mode, **kw)


def load_case(case: str) -> dict:
    return json.loads((GOLDEN / case / "input.json").read_text())


def provider_of(form_code: str) -> str:
    return form_code.split(".")[0]


def put_evidence(docs, org_id: str, raw: list[dict]) -> list[dict]:
    """Store each fixture evidence file and return the port's evidence list [{metric, document_id, title}]."""
    out = []
    for e in raw:
        doc_id = docs.put(
            org_id, filename=e["filename"], content_type="application/octet-stream", content=e["content"].encode()
        )
        out.append({"metric": e["metric"], "document_id": doc_id, "title": e["title"]})
    return out


def prepare(adapter, org, docs, case: dict, key: str | None = None, **overrides):
    """Prepare a fixture case through the adapter; returns the Result."""
    case = copy.deepcopy(case)
    args = {
        "package_key": key if key is not None else str(uuid.uuid4()),
        "form_code": case["form_code"],
        "period": case["period"],
        "data": case["data"],
        "evidence": put_evidence(docs, org.id, case["evidence"]),
    }
    args.update(overrides)
    return adapter.prepare_package(org.ctx(provider_of(case["form_code"])), **args)


def outbox(org_id: str, name: str) -> list[OutboxEvent]:
    with platform_scope(), SessionLocal() as db:
        return list(
            db.execute(
                select(OutboxEvent).where(OutboxEvent.organisation_id == org_id, OutboxEvent.name == name)
            ).scalars()
        )
