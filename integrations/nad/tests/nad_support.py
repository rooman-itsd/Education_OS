"""Helpers shared by the nad tests (kept out of conftest.py so test files can import them)."""

import copy
import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from eos_core.db import SessionLocal
from eos_core.security import create_token
from eos_core.tenant import platform_scope
from sqlalchemy import select

FIXTURES = Path(__file__).parent / "fixtures"
NOW = datetime(2026, 11, 5, 4, 30, 0, tzinfo=UTC)
PREFIX = "/api/v1/nad"


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
    """JSON inputs are returned as a fresh object each time; anything else as bytes."""
    path = FIXTURES / name
    return json.loads(path.read_text()) if name.endswith(".json") else path.read_bytes()


def settings(**overrides) -> dict:
    s = {
        "nad_institution_id": "NAD-INST-0042",
        "abc_institution_id": "ABC-INST-0042",
        "institution_name": "Example College of Science",
        "award_templates": [
            {"award_kind": "degree", "template_code": "DEG-UG-01", "programme_level": "undergraduate"},
            {"award_kind": "marksheet", "template_code": "MS-UG-01"},
            {"award_kind": "grade_card", "template_code": "GC-UG-01"},
        ],
    }
    s.update(overrides)
    return s


def ctx(org: Org, *, mode="mock", **overrides) -> dict:
    c = {
        "organisation_id": org.id,
        "connection_id": str(uuid.uuid4()),
        "provider": "nad",
        "mode": mode,
        "settings": settings(),
        "secrets": {},
        "account_link": None,
        "delivery_id": str(uuid.uuid4()),
        "attempt": 1,
        "idempotency_key": "k",
    }
    c.update(overrides)
    return c


def awards_batch(**overrides) -> dict:
    batch = fixture("awards_batch.json")
    batch.update(overrides)
    return copy.deepcopy(batch)


def credits_batch(**overrides) -> dict:
    batch = fixture("credits_batch.json")
    batch.update(overrides)
    return copy.deepcopy(batch)


def record(i: int, **overrides) -> dict:
    """A valid degree record; i makes the learner, award number and APAAR id unique."""
    rec = {
        "learner": {
            "person_id": str(uuid.uuid4()),
            "apaar_id": f"{100000000000 + i}",
            "enrolment_number": f"EN-2023-{i:04d}",
            "name": f"Learner {i}",
            "date_of_birth": "2004-03-15",
            "gender": "F",
        },
        "award_number": f"DEG-2026-{i:04d}",
        "result": {
            "cgpa": 8.4,
            "percentage": 84.0,
            "division": "First Class with Distinction",
            "result_status": "pass",
        },
        "courses": [],
        "term": "6",
        "issued_on": "2026-10-30",
    }
    rec.update(overrides)
    return rec


def ok(result: dict) -> dict:
    assert "error" not in result, result
    return result["output"]


def err(result: dict) -> dict:
    assert "output" not in result, result
    return result["error"]


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
