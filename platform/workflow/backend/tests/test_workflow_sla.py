"""SLA escalation (#317 follow-up): a step past its deadline is escalated once by the scheduled workflow.sla-check
job, which records it and publishes workflow.step.overdue. Before, the deadline was only computed when read, a step
without sla_hours had none, and WORKFLOW_DEFAULT_SLA_HOURS was read by nothing."""

from __future__ import annotations

import tomllib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from eos_workflow.application import consumers, jobs, service
from eos_workflow.domain.models import WorkflowEscalation
from sqlalchemy import select
from workflow_support import Org, sample_chain

LATER = datetime.now(UTC) + timedelta(days=30)  # every 24 h / 48 h deadline is long past by then


def _request(db, org, chain=None):
    data = chain or sample_chain(f"c{uuid.uuid4().hex[:6]}")
    service.create_chain(db, org.id, data["code"], data["title"], None, data["steps"])
    req, _ = service.create_request(db, org.id, data["code"], "leave", "e-1", "Leave", requester_id=org.student.id)
    db.commit()
    return req


def _escalate(now=LATER) -> int:
    with platform_scope(), SessionLocal() as db:
        return service.escalate_overdue(db, now=now)


def _overdue_events() -> list[dict]:
    with platform_scope(), SessionLocal() as db:
        return [e.payload | {"_org": e.organisation_id} for e in db.scalars(
            select(OutboxEvent).where(OutboxEvent.name == "workflow.step.overdue")
        )]  # fmt: skip


def _escalations() -> list[WorkflowEscalation]:
    with platform_scope(), SessionLocal() as db:
        return list(db.scalars(select(WorkflowEscalation)))


def test_a_step_without_its_own_sla_gets_the_default_deadline(workflow_db, monkeypatch):
    monkeypatch.setenv("WORKFLOW_DEFAULT_SLA_HOURS", "6")
    org = Org(workflow_db)
    steps = [{"step_order": 1, "name": "HoD", "approver_role": "department-admin", "is_final": True}]
    before = datetime.now(UTC)
    req = _request(workflow_db, org, {"code": "nosla", "title": "No SLA", "steps": steps})
    deadline = (
        req.current_step_deadline.replace(tzinfo=UTC)
        if req.current_step_deadline.tzinfo is None
        else req.current_step_deadline
    )
    assert before + timedelta(hours=6) - timedelta(seconds=5) <= deadline <= datetime.now(UTC) + timedelta(hours=6)


def test_an_overdue_step_is_escalated_once(workflow_db):
    org = Org(workflow_db)
    req = _request(workflow_db, org)
    assert _escalate() == 1
    assert _escalate() == 0  # a second check, or a retry: nothing new
    (event,) = _overdue_events()
    assert event["request_id"] == req.id and event["step_order"] == 1 and event["approver_role"] == "department-admin"
    assert event["_org"] == org.id and event["overdue_seconds"] > 0
    (row,) = _escalations()
    assert (row.request_id, row.step_order, row.organisation_id) == (req.id, 1, org.id)


def test_nothing_is_escalated_before_the_deadline_or_after_a_decision(workflow_db):
    org = Org(workflow_db)
    _request(workflow_db, org)
    assert _escalate(now=datetime.now(UTC)) == 0  # 24 h to go
    done = _request(workflow_db, org)
    service.reject_request(workflow_db, org.id, done.id, org.dept_admin.id, actor_roles=["department-admin"])
    workflow_db.commit()
    assert _escalate() == 1  # only the first, still-pending request
    assert {e["request_id"] for e in _overdue_events()} != {done.id}


def test_the_next_step_is_escalated_again_when_it_is_late_too(workflow_db):
    org = Org(workflow_db)
    req = _request(workflow_db, org)
    assert _escalate() == 1
    service.approve_request(workflow_db, org.id, req.id, org.dept_admin.id, actor_roles=["department-admin"])
    workflow_db.commit()
    assert _escalate(now=LATER + timedelta(days=30)) == 1
    assert sorted(e["step_order"] for e in _overdue_events()) == [1, 2]


def test_each_organisations_escalation_stays_in_that_organisation(workflow_db):
    a, b = Org(workflow_db), Org(workflow_db)
    _request(workflow_db, a)
    _request(workflow_db, b)
    assert _escalate() == 2
    with organisation_scope(a.id), SessionLocal() as db:
        from eos_core.db import scoped

        visible = db.scalars(scoped(db, select(WorkflowEscalation), WorkflowEscalation)).all()
    assert [r.organisation_id for r in visible] == [a.id]


# --- the scheduled job -------------------------------------------------------------------------------------------


def test_the_sla_check_is_declared_for_the_scheduler():
    assert jobs.JOBS["workflow.sla-check"]["scope"] == "platform" and jobs.JOBS["workflow.sla-check"]["idempotent"]
    pyproject = tomllib.loads((Path(__file__).resolve().parents[1] / "pyproject.toml").read_text())
    points = pyproject["project"]["entry-points"]
    assert points["eos.scheduler_jobs"] == {"workflow": "eos_workflow.application.jobs:JOBS"}
    assert points["eos.event_consumers"] == {"workflow": "eos_workflow.application.consumers:CONSUMERS"}


def _due(job="workflow.sla-check"):
    return SimpleNamespace(id=str(uuid.uuid4()), name="scheduler.job.due", organisation_id=None,
                           payload={"job": job, "run_id": str(uuid.uuid4())}, actor=None)  # fmt: skip


def _finished(run_id):
    with platform_scope(), SessionLocal() as db:
        return [e.payload for e in db.scalars(select(OutboxEvent).where(OutboxEvent.name == "workflow.job.finished"))
                if e.payload.get("run_id") == run_id]  # fmt: skip


def test_the_job_escalates_and_reports_the_run(workflow_db, monkeypatch):
    org = Org(workflow_db)
    _request(workflow_db, org)
    monkeypatch.setattr(service, "utcnow", lambda: LATER)
    e = _due()
    with platform_scope(), SessionLocal() as db:
        consumers.on_job_due(db, e)
        db.commit()
    (report,) = _finished(e.payload["run_id"])
    assert report["outcome"] == "succeeded" and report["detail"] == "1 overdue step(s) escalated"


def test_the_job_ignores_other_jobs_and_reports_its_own_failure(monkeypatch):
    other = _due("billing.expire-trials")
    with platform_scope(), SessionLocal() as db:
        consumers.on_job_due(db, other)
        db.commit()
    assert _finished(other.payload["run_id"]) == []

    def broken(db, now=None):
        raise RuntimeError("db down")

    monkeypatch.setattr(service, "escalate_overdue", broken)
    e = _due()
    with platform_scope(), SessionLocal() as db:
        consumers.on_job_due(db, e)
        db.commit()
    (report,) = _finished(e.payload["run_id"])
    assert report == {"run_id": e.payload["run_id"], "outcome": "failed", "detail": "RuntimeError"}
