"""contracts/events.yaml against what the service publishes: every event workflow raises, driven through the real
service, carries exactly the payload keys its contract entry declares, with values of the declared type (a trailing
`?` allows null). Before, five of the seven events declared no payload, so a consumer (examinations reacting to a
result set's approval) could not rely on any field."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import yaml
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import platform_scope
from eos_workflow.application import consumers, service
from sqlalchemy import select
from workflow_support import Org

CONTRACT = yaml.safe_load(
    (Path(__file__).resolve().parents[2] / "contracts" / "events.yaml").read_text(encoding="utf-8")
)
DECLARED = {e["name"]: e for e in CONTRACT["events"]}
ENVELOPE_FIELDS = {"id", "name", "version", "organisation_id", "actor", "occurred_at"}


def _is_uuid(v) -> bool:
    try:
        uuid.UUID(str(v))
    except ValueError:
        return False
    return isinstance(v, str)


def _is_datetime(v) -> bool:
    try:
        datetime.fromisoformat(v)
    except (TypeError, ValueError):
        return False
    return True


CHECKS = {
    "uuid": _is_uuid,
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "datetime": _is_datetime,
}


def _matches(declared: str, value) -> bool:
    if declared.endswith("?"):
        return value is None or _matches(declared[:-1], value)
    return CHECKS[declared](value)


def _chain(db, org, code):
    service.create_chain(
        db,
        org.id,
        code,
        "Result approval",
        None,
        [
            {"step_order": 1, "name": "HoD", "approver_role": "department-admin", "sla_hours": 24},
            {"step_order": 2, "name": "Controller", "approver_role": "org-admin", "is_final": True},
        ],
    )


def _submit(db, org, code, entity_id):
    req, _ = service.create_request(
        db, org.id, code, "examinations.result_set", entity_id, "Results", requester_id=org.faculty.id
    )
    return req


def _publish_every_event(db, org) -> None:
    """Submit, delegate, advance, approve, reject, escalate and finish a job: every event workflow publishes."""
    code = f"results-{uuid.uuid4().hex[:6]}"
    _chain(db, org, code)
    approved = _submit(db, org, code, "rs-1")
    service.delegate_request(
        db, org.id, approved.id, org.admin.id, org.dept_admin.id, actor_roles=["org-admin"], comments=None
    )
    service.approve_request(db, org.id, approved.id, org.dept_admin.id, actor_roles=["department-admin"])
    service.approve_request(db, org.id, approved.id, org.admin.id, actor_roles=["org-admin"], comments="Signed")
    rejected = _submit(db, org, code, "rs-2")
    service.reject_request(db, org.id, rejected.id, org.dept_admin.id, actor_roles=["department-admin"])
    _submit(db, org, code, "rs-3")
    db.commit()
    with platform_scope(), SessionLocal() as s:
        assert service.escalate_overdue(s, now=datetime.now(UTC) + timedelta(days=30)) >= 1
    due = SimpleNamespace(
        id=str(uuid.uuid4()),
        name="scheduler.job.due",
        organisation_id=None,
        payload={"job": "workflow.sla-check", "run_id": str(uuid.uuid4())},
        actor=None,
    )
    with platform_scope(), SessionLocal() as s:
        consumers.on_job_due(s, due)
        s.commit()


def _published() -> list[OutboxEvent]:
    with platform_scope(), SessionLocal() as s:
        return list(s.scalars(select(OutboxEvent).where(OutboxEvent.name.like("workflow.%"))))


def test_every_event_declares_a_payload_without_envelope_fields():
    for name, entry in DECLARED.items():
        assert entry.get("payload"), f"{name} declares no payload"
        assert not ENVELOPE_FIELDS & set(entry["payload"]), name
        for key, declared in entry["payload"].items():
            assert declared.rstrip("?") in CHECKS, f"{name}.{key}: unknown type {declared!r}"


def test_every_published_event_matches_its_declared_payload(workflow_db):
    org = Org(workflow_db)
    _publish_every_event(workflow_db, org)

    published = _published()
    assert {e.name for e in published} == set(DECLARED)  # every declared event was exercised, none undeclared
    for event in published:
        declared = DECLARED[event.name]["payload"]
        assert set(event.payload) == set(declared), event.name
        for key, value in event.payload.items():
            assert _matches(declared[key], value), f"{event.name}.{key} = {value!r} is not {declared[key]}"


def test_the_nullable_fields_are_null_when_nothing_was_said(workflow_db):
    """comments is optional on every decision; the `?` in the contract is what lets a consumer expect None."""
    org = Org(workflow_db)
    _publish_every_event(workflow_db, org)
    by_name = {}
    for event in _published():
        by_name.setdefault(event.name, []).append(event.payload)
    assert by_name["workflow.request.rejected"][0]["comments"] is None
    assert by_name["workflow.request.delegated"][0]["comments"] is None
    assert by_name["workflow.request.approved"][0]["comments"] == "Signed"
    assert DECLARED["workflow.request.approved"]["payload"]["comments"] == "string?"
