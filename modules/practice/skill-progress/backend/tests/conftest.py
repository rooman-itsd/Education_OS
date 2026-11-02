"""The module's tests run alone (module standard rule 6): only eos_core, eos_testing and this package.
The database is always a throwaway SQLite file. EOS_DATABASE_URL is overwritten, not defaulted, so a
shell that points at a real database can never be reached from these tests."""

import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

os.environ["EOS_DATABASE_URL"] = f"sqlite:///{tempfile.mkdtemp()}/skill_progress_test.db"
os.environ.setdefault("EOS_REPO_ROOT", str(Path(__file__).resolve().parents[5]))

import pytest
from eos_core.db import SessionLocal, init_db, new_id
from eos_core.events import OutboxEvent
from eos_core.security import create_token
from eos_skill_progress.api.router import router
from eos_skill_progress.application import service
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

NOW = datetime(2026, 10, 30, 9, 0, tzinfo=UTC)
BASE = "/api/v1/skill-progress"
ADMIN = "skill-progress-admin"
EVALUATOR = "skill-progress-evaluator"
VIEWER = "skill-progress-viewer"
# Profile roles (platform/identity/config/dashboards): a learner role that extends student and holds the viewer
# role, and a coordinator who holds the viewer role without being a learner.
LEARNER = "musician"
COORDINATOR = "practicum-coordinator"

SCALE = {
    "type": "numeric_range",
    "min_score": 0,
    "max_score": 100,
    "levels": [
        {"key": "novice", "label": "Novice", "rank": 1, "min_score": 0},
        {"key": "developing", "label": "Developing", "rank": 2, "min_score": 40},
        {"key": "proficient", "label": "Proficient", "rank": 3, "min_score": 70},
        {"key": "expert", "label": "Expert", "rank": 4, "min_score": 90},
    ],
}
CRITERIA = [
    {"key": "technique", "title": "Technique", "weight": 2, "max_points": 10},
    {
        "key": "expression",
        "title": "Expression",
        "max_points": 10,
        "levels": [
            {"key": "weak", "label": "Weak", "rank": 1},
            {"key": "strong", "label": "Strong", "rank": 2, "min_score": 6},
        ],
    },
]


@pytest.fixture(scope="session")
def client():
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    init_db()
    with TestClient(app) as c:
        yield c


@pytest.fixture(autouse=True)
def frozen_clock(monkeypatch):
    monkeypatch.setattr(service, "clock", lambda: NOW)
    return NOW


class Org:
    """One organisation with helpers to mint users and seed frameworks, skills and rubrics through the API."""

    def __init__(self, client) -> None:
        self.id = new_id()
        self.client = client
        self.admin_id, self.admin = self.user(ADMIN)
        self.evaluator_id, self.evaluator = self.user(EVALUATOR)

    def user(self, *roles: str, user_id: str | None = None) -> tuple[str, dict]:
        user_id = user_id or new_id()
        token = create_token(user_id=user_id, organisation_id=self.id, roles=list(roles))
        return user_id, {"Authorization": f"Bearer {token}"}

    def post(self, path: str, body: dict, headers: dict | None = None) -> dict:
        r = self.client.post(f"{BASE}{path}", json=body, headers=headers or self.admin)
        assert r.status_code == 201, r.text
        return r.json()

    def framework(self, code: str = "PRAC-2026", **kw) -> dict:
        return self.post("/frameworks", {"code": code, "title": "Core practical competencies", **kw})

    def skill(self, framework_id: str, code: str = "SKILL-01", scale: dict | None = None, **kw) -> dict:
        body = {"framework_id": framework_id, "code": code, "title": f"Technique {code}", "level_scale": scale or SCALE}
        return self.post("/skills", {**body, **kw})

    def rubric(self, skill_id: str | None = None, framework_id: str | None = None, **kw) -> dict:
        body = {"title": "Practicum rubric", "criteria": CRITERIA, **kw}
        if skill_id:
            body["skill_id"] = skill_id
        if framework_id:
            body["framework_id"] = framework_id
        return self.post("/rubrics", body)

    def setup(self) -> tuple[dict, dict, dict]:
        f = self.framework()
        s = self.skill(f["id"])
        return f, s, self.rubric(s["id"])

    def body(self, learner_id: str, skill: dict, rubric: dict, score: float = 75, level: str = "Proficient", **kw):
        return {
            "learner_id": learner_id,
            "evaluator_id": self.evaluator_id,
            "skill_id": skill["id"],
            "rubric_id": rubric["id"],
            "criterion_scores": [
                {"criterion_key": "technique", "points": 8},
                {"criterion_key": "expression", "points": 7, "level_key": "strong"},
            ],
            "overall_score": score,
            "level_achieved": level,
            **kw,
        }

    def assess(self, learner_id: str, skill: dict, rubric: dict, score=75, level="Proficient", **kw) -> dict:
        return self.post("/assessments", self.body(learner_id, skill, rubric, score, level, **kw), self.evaluator)


@pytest.fixture
def org(client) -> Org:
    return Org(client)


@pytest.fixture
def other_org(client) -> Org:
    return Org(client)


def outbox(organisation_id: str, name: str | None = None) -> list[OutboxEvent]:
    with SessionLocal() as db:
        q = select(OutboxEvent).where(OutboxEvent.organisation_id == organisation_id)
        if name:
            q = q.where(OutboxEvent.name == name)
        return list(db.scalars(q.order_by(OutboxEvent.occurred_at, OutboxEvent.id)))
