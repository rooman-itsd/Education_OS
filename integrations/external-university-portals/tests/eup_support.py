"""Helpers shared by the external-university-portals tests."""

import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from eos_external_university_portals.domain.port import Context
from sqlalchemy import select

PREFIX = "/api/v1/external-university-portals"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
FIXED_NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=UTC)
PROVIDER_OF = {"pdf": "file", "csv": "file", "elmo_xml": "elmo", "edc_jsonld": "edc"}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def transcript() -> dict:
    return copy.deepcopy(json.loads((FIXTURES / "transcript.json").read_text()))


def partner(**overrides) -> dict:
    s = {
        "partner_id": "uni-oslo",
        "name": "University of Oslo",
        "country": "NO",
        "institution_code": "NO OSLO01",
        "channel": "download",
    }
    s.update(overrides)
    return s


class Org:
    """An organisation with an org admin and a student, each with a platform token."""

    def __init__(self, org_id: str | None = None):
        self.id = org_id or str(uuid.uuid4())
        self.admin_id, self.student_id = str(uuid.uuid4()), str(uuid.uuid4())
        self.admin = auth(create_token(user_id=self.admin_id, organisation_id=self.id, roles=["org-admin"]))
        self.student = auth(create_token(user_id=self.student_id, organisation_id=self.id, roles=["student"]))

    def token(self, who: str) -> str:
        return getattr(self, who)["Authorization"].split(" ", 1)[1]

    def ctx(self, provider: str = "file", mode: str = "mock", settings: dict | None = None, **kw) -> Context:
        return Context(
            organisation_id=self.id,
            provider=provider,
            mode=mode,
            settings=partner() if settings is None else settings,
            **kw,
        )


def export(
    adapter, org, fmt: str, key: str | None = None, settings: dict | None = None, mode: str = "mock", **overrides
):
    args = {
        "exchange_key": key if key is not None else str(uuid.uuid4()),
        "partner_id": "uni-oslo",
        "format": fmt,
        "transcript": transcript(),
    }
    args.update(overrides)
    return adapter.export_records(org.ctx(PROVIDER_OF.get(fmt, "file"), mode, settings), **args)


def put(docs, org_id: str, content: bytes, filename: str = "file.bin") -> str:
    return docs.put(org_id, filename=filename, content_type="application/octet-stream", content=content)


def outbox(org_id: str, name: str) -> list[OutboxEvent]:
    with platform_scope(), SessionLocal() as db:
        return list(
            db.execute(
                select(OutboxEvent).where(OutboxEvent.organisation_id == org_id, OutboxEvent.name == name)
            ).scalars()
        )
