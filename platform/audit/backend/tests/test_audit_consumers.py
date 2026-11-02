"""Audit is fed by the outbox (#317 follow-up): other modules' state-change events become append-only records,
super admin operations also become platform-level records, a redelivered event records nothing twice, and the
scheduler's audit.prune job runs retention."""

from __future__ import annotations

import tomllib
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml
from eos_audit.application import consumers, jobs, service
from eos_audit.application.service import AuditError
from eos_audit.domain.models import AuditRecord
from eos_core.db import SessionLocal
from eos_core.events import OutboxEvent
from eos_core.tenant import organisation_scope, platform_scope
from sqlalchemy import select

MODULE_DIR = Path(__file__).resolve().parents[2]


def event(name, organisation_id, payload=None, *, actor=None, occurred_at=None):
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        name=name,
        organisation_id=organisation_id,
        payload=payload or {},
        actor=actor,
        version=1,
        occurred_at=occurred_at or datetime.now(UTC) - timedelta(minutes=5),
    )


def deliver(e) -> None:
    """As the relay delivers: a session of its own, in the event's organisation (platform scope without one)."""
    scope = organisation_scope(e.organisation_id) if e.organisation_id else platform_scope()
    with scope, SessionLocal() as db:
        consumers.CONSUMERS[e.name](db, e)
        db.commit()


def records(organisation_id: str | None = None, *, platform: bool = False) -> list[AuditRecord]:
    with platform_scope(), SessionLocal() as db:
        q = select(AuditRecord)
        q = (
            q.where(AuditRecord.organisation_id.is_(None))
            if platform
            else q.where(AuditRecord.organisation_id == organisation_id)
        )
        return list(db.scalars(q.order_by(AuditRecord.occurred_at)))


def test_a_state_change_event_becomes_one_record_in_its_organisation():
    org = str(uuid.uuid4())
    when = datetime(2026, 11, 1, 9, 30, tzinfo=UTC)
    deliver(
        event(
            "tenancy.organisation.registered",
            org,
            {"organisation_id": org, "slug": "harmony", "academy_type": "music-academy"},
            occurred_at=when,
        )
    )
    (rec,) = records(org)
    assert (rec.module, rec.action, rec.entity_type, rec.entity_id) == (
        "tenancy",
        "organisation.registered",
        "organisation",
        org,
    )
    assert rec.actor is None and rec.after["slug"] == "harmony"
    assert service._utc(rec.occurred_at) == when  # the event's time, not when audit received it
    assert rec.context["source"] == "event-bus" and rec.context["event_id"]
    assert records(platform=True) == []  # a registration is not a super admin action


def test_a_redelivered_event_records_nothing_twice():
    org = str(uuid.uuid4())
    e = event("workflow.request.approved", org, {"request_id": "req-1", "approved_by": "u-1"}, actor="u-1")
    deliver(e)
    deliver(e)
    (rec,) = records(org)
    assert (rec.entity_type, rec.entity_id, rec.actor) == ("request", "req-1", "u-1")


def test_a_super_admin_action_is_also_recorded_at_platform_level():
    org = str(uuid.uuid4())
    e = event(
        "tenancy.impersonation.started",
        org,
        {"organisation_id": org, "user_id": "user-9", "super_admin_id": "sa-1", "reason": "support ticket 42"},
        actor="sa-1",
    )
    deliver(e)
    deliver(e)  # redelivery: still one of each
    (in_org,) = records(org)
    (platform,) = records(platform=True)
    for rec in (in_org, platform):
        assert rec.action == "impersonation.started" and rec.actor == "sa-1" and rec.entity_id == "user-9"
    assert platform.context["organisation_id"] == org  # which organisation the operation touched
    assert in_org.client_token != platform.client_token


def test_a_platform_event_without_an_organisation_is_recorded_once_at_platform_level():
    org = str(uuid.uuid4())
    deliver(event("tenancy.organisation.purged", None, {"organisation_id": org, "slug": "gone"}, actor="sa-2"))
    (rec,) = records(platform=True)
    assert rec.action == "organisation.purged" and rec.entity_id == org and rec.actor == "sa-2"


def test_secret_looking_keys_are_dropped_and_named_not_refused():
    """The audit contract refuses a payload with a secret-looking key; an event carrying one must still be
    recorded (that it happened), without the value, rather than be retried until dead-lettered."""
    org = str(uuid.uuid4())
    deliver(
        event(
            "identity.user.created",
            org,
            {"user_id": "u-7", "email": "a@b.example", "reset_token": "abc", "nested": {"password": "x", "ok": 1}},
        )
    )
    (rec,) = records(org)
    assert rec.after == {"user_id": "u-7", "email": "a@b.example", "nested": {"ok": 1}}
    assert rec.context["dropped_keys"] == ["password", "reset_token"]


def test_a_record_audit_cannot_store_raises_so_the_relay_retries(monkeypatch):
    monkeypatch.setenv("AUDIT_MAX_PAYLOAD_BYTES", "64")
    org = str(uuid.uuid4())
    with pytest.raises(AuditError):
        deliver(event("documents.document.uploaded", org, {"document_id": "d-1", "filename": "x" * 500}))
    assert records(org) == []


def test_every_audited_event_is_declared_and_handled():
    contract = yaml.safe_load((MODULE_DIR / "contracts" / "events.yaml").read_text())
    manifest = yaml.safe_load((MODULE_DIR / "module.yaml").read_text())
    expected = [*consumers.AUDITED, "scheduler.job.due"]
    assert contract["consumes"] == expected
    assert manifest["consumes_events"] == expected
    assert set(consumers.CONSUMERS) == set(expected)
    assert consumers.SUPER_ADMIN_ACTIONS <= set(consumers.AUDITED)
    pyproject = tomllib.loads((MODULE_DIR / "backend" / "pyproject.toml").read_text())
    entry_points = pyproject["project"]["entry-points"]
    assert entry_points["eos.event_consumers"] == {"audit": "eos_audit.application.consumers:CONSUMERS"}
    assert entry_points["eos.scheduler_jobs"] == {"audit": "eos_audit.application.jobs:JOBS"}


# --- audit.prune ---------------------------------------------------------------------------------------------


def job_due(job=jobs.PRUNE):
    return SimpleNamespace(
        id=str(uuid.uuid4()),
        name="scheduler.job.due",
        organisation_id=None,
        payload={"job": job, "run_id": str(uuid.uuid4())},
        actor=None,
    )


def finished(run_id: str) -> list[dict]:
    with platform_scope(), SessionLocal() as db:
        rows = db.scalars(select(OutboxEvent).where(OutboxEvent.name == "audit.job.finished")).all()
        return [r.payload for r in rows if r.payload.get("run_id") == run_id]


def test_the_prune_job_removes_expired_records_and_reports_the_run(monkeypatch):
    monkeypatch.setenv("AUDIT_RETENTION_ENABLED", "true")
    org = str(uuid.uuid4())
    old = datetime.now(UTC) - timedelta(days=service.config.retention_days() + 1)
    deliver(event("billing.invoice.paid", org, {"invoice_id": "inv-old"}, occurred_at=old))
    deliver(event("billing.invoice.paid", org, {"invoice_id": "inv-new"}))
    e = job_due()
    deliver(e)
    assert [r.entity_id for r in records(org)] == ["inv-new"]
    (report,) = finished(e.payload["run_id"])
    assert report["outcome"] == "succeeded" and report["detail"] == "1 record(s) removed"


def test_the_prune_job_ignores_other_jobs_and_reports_its_own_failure(monkeypatch):
    other = job_due("billing.expire-trials")
    deliver(other)
    assert finished(other.payload["run_id"]) == []

    def broken(db, **kwargs):
        raise RuntimeError("disk full")

    monkeypatch.setattr(service, "prune", broken)
    e = job_due()
    deliver(e)  # reported, not raised
    (report,) = finished(e.payload["run_id"])
    assert report == {"run_id": e.payload["run_id"], "outcome": "failed", "detail": "RuntimeError"}


# --- a purged organisation's trail is kept, its payloads redacted (decision on #317) ------------------------------


def test_purging_an_organisation_redacts_its_trail_but_keeps_the_facts():
    org, other = str(uuid.uuid4()), str(uuid.uuid4())
    deliver(event("workflow.request.approved", org, {"request_id": "r1", "comments": "medical leave"}, actor="u1"))
    deliver(event("tenancy.impersonation.started", org, {"user_id": "u9", "reason": "ticket 7"}, actor="sa-1"))
    deliver(event("workflow.request.approved", other, {"request_id": "r2", "comments": "keep me"}, actor="u2"))
    purged = event("tenancy.organisation.purged", None, {"organisation_id": org, "slug": "gone"}, actor="sa-1")
    deliver(purged)
    deliver(purged)  # redelivered: nothing changes twice

    mine = records(org)
    assert [r.action for r in mine] == ["request.approved", "impersonation.started"]
    assert all(r.redacted and r.after is None and r.before is None for r in mine)
    assert all(r.actor and r.entity_id for r in mine)  # who did what, and to which entity, survives
    platform = records(platform=True)
    copy = next(r for r in platform if r.action == "impersonation.started")
    assert copy.redacted and copy.after is None
    purge_record = next(r for r in platform if r.action == "organisation.purged")
    assert not purge_record.redacted and purge_record.after["slug"] == "gone"  # the purge itself is the record
    (theirs,) = records(other)
    assert not theirs.redacted and theirs.after["comments"] == "keep me"


def test_the_purge_event_is_handled_by_the_purge_handler():
    assert consumers.CONSUMERS["tenancy.organisation.purged"] is consumers.on_purged
