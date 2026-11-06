"""Events against contracts/events.yaml, and the outbox rule: an event and its audit entry are written in the same
transaction as the change, so a failure leaves none of the three."""

import uuid
from datetime import datetime
from pathlib import Path

import pytest
import yaml
from conftest import BASE, all_events, audit_actions
from eos_core.db import SessionLocal
from eos_lms.application import common
from eos_lms.infrastructure.models import CourseSpace
from sqlalchemy import select
from test_contract import journey

EVENTS = yaml.safe_load((Path(__file__).resolve().parents[2] / "contracts" / "events.yaml").read_text(encoding="utf-8"))
DECLARED = {e["name"]: e for e in EVENTS["events"]}


def matches(value, kind: str) -> bool:
    optional = kind.endswith("?")
    kind = kind.rstrip("?")
    if value is None:
        return optional
    if kind.endswith("[]"):
        return isinstance(value, list) and all(matches(v, kind[:-2]) for v in value)
    if kind == "uuid":
        return isinstance(value, str) and str(uuid.UUID(value)) == value.lower()
    if kind == "datetime":
        return isinstance(value, str) and datetime.fromisoformat(value).tzinfo is not None
    if kind == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "number":
        return isinstance(value, int | float) and not isinstance(value, bool)
    if kind == "boolean":
        return isinstance(value, bool)
    return isinstance(value, str)


def test_every_declared_event_is_published_with_its_declared_payload(client, org, monkeypatch):
    journey(client, org, monkeypatch)
    published = all_events(org.id)
    assert {e.name for e in published} == set(DECLARED)
    for e in published:
        declared = DECLARED[e.name]["payload"]
        assert set(e.payload) == set(declared), e.name
        for key, kind in declared.items():
            assert matches(e.payload[key], kind), (e.name, key, e.payload[key], kind)
        assert e.payload["organisation_id"] == e.organisation_id == org.id, e.name
        assert e.actor is not None, e.name  # every event of the journey has a person behind it


def test_names_follow_the_module_convention():
    for name in DECLARED:
        module, entity, verb = name.split(".")
        assert module == "lms" and entity and verb.endswith("ed"), name


def test_a_failure_after_the_event_leaves_no_change_no_event_and_no_audit(client, org, monkeypatch, course):
    c = course
    before = len(all_events(org.id))
    original = common.publish

    def publish_then_fail(*args, **kwargs):
        original(*args, **kwargs)
        raise RuntimeError("broker down")

    monkeypatch.setattr(common, "publish", publish_then_fail)
    m = c.material(publish=False)
    with pytest.raises(RuntimeError):
        client.post(f"{BASE}/materials/{m['id']}/status", json={"status": "published"}, headers=c.teacher)
    monkeypatch.setattr(common, "publish", original)
    assert len(all_events(org.id)) == before
    assert c.get(f"/materials/{m['id']}", c.teacher)["status"] == "draft"
    assert "material.published" not in audit_actions(org.id, m["id"])
    # The same request, without the failure, writes all three.
    c.post(f"/materials/{m['id']}/status", {"status": "published"}, headers=c.teacher)
    assert len(all_events(org.id)) == before + 1
    assert "material.published" in audit_actions(org.id, m["id"])


def test_a_failed_creation_leaves_no_row(client, org, monkeypatch):
    from conftest import ADMIN, deliver, offering_created
    from eos_lms.application import consumers as cons

    offering = str(uuid.uuid4())
    deliver(org.id, cons.OFFERING_CREATED, offering_created(offering))
    _, admin = org.user(ADMIN)

    def fail(*args, **kwargs):
        raise RuntimeError("audit store down")

    monkeypatch.setattr(common, "audit", fail)
    with pytest.raises(RuntimeError):
        client.post(f"{BASE}/course-spaces", json={"course_offering_id": offering, "title": "x"}, headers=admin)
    with SessionLocal() as db:
        assert db.scalars(select(CourseSpace).where(CourseSpace.course_offering_id == offering)).first() is None
    assert all_events(org.id) == []
