"""Audit is fed by the outbox (#317 follow-up): other modules' state-change events become append-only records,
super admin operations also become platform-level records, a redelivered event records nothing twice, and the
scheduler's audit.prune job runs retention."""

from __future__ import annotations

import re
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
    assert rec.after == {
        "user_id": "u-7",
        "nested": {"ok": 1},
    }  # the email is dropped too: see the contact-detail tests
    assert rec.context["dropped_keys"] == ["email", "password", "reset_token"]


EMAIL = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def stored_text(e) -> str:
    """Everything audit stored for one event, in the organisation and at platform level, as one string."""
    found = [
        r for r in records(e.organisation_id) + records(platform=True) if (r.context or {}).get("event_id") == e.id
    ]
    assert found, "the event recorded nothing"
    return repr([(r.before, r.after, r.context, r.entity_id, r.actor) for r in found])


def test_the_registration_email_never_reaches_an_immutable_record():
    """Review of #434: tenancy.organisation.registered carries admin_email, and a record cannot be edited, so the
    address could never be removed when its owner asks for erasure. It is dropped; the record says it was there."""
    org = str(uuid.uuid4())
    e = event(
        "tenancy.organisation.registered",
        org,
        {
            "organisation_id": org,
            "slug": "harmony",
            "academy_type": "music-academy",
            "admin_email": "owner@harmony.example",
        },
    )
    deliver(e)
    (rec,) = records(org)
    assert rec.after == {"organisation_id": org, "slug": "harmony", "academy_type": "music-academy"}
    assert rec.context["dropped_keys"] == ["admin_email"]
    assert not EMAIL.search(stored_text(e)) and "owner@harmony" not in stored_text(e)


def test_the_platform_copy_of_a_super_admin_action_carries_no_email_either():
    """A super admin action is recorded twice (in the organisation and at platform level); the one cleaned payload
    feeds both, so neither can keep an address. registered is a self-registration, not a super admin action, so
    the check uses suspended, whose operator-typed reason may well contain one."""
    org = str(uuid.uuid4())
    e = event(
        "tenancy.organisation.suspended",
        org,
        {"organisation_id": org, "admin_email": "a@b.example", "reason": "mail bounced from c@d.example"},
        actor="sa-1",
    )
    deliver(e)
    (in_org,) = records(org)
    (platform_rec,) = [r for r in records(platform=True) if (r.context or {}).get("event_id") == e.id]
    for rec in (in_org, platform_rec):
        assert rec.after == {"organisation_id": org}
        assert rec.context["dropped_keys"] == ["admin_email", "reason"]
    assert not EMAIL.search(stored_text(e))


def test_an_email_address_is_dropped_whatever_its_key_is_called():
    """The key rule catches admin_email; the value rule catches the next event that puts an address under a
    harmless-looking name, or inside a sentence."""
    org = str(uuid.uuid4())
    e = event(
        "tenancy.organisation.suspended",
        org,
        {
            "organisation_id": org,
            "reason": "bounced mail to bob@example.com",
            "note": "ok",
            "contact": "bob@example.com",
        },
    )
    deliver(e)
    (rec,) = records(org)
    assert rec.after == {"organisation_id": org, "note": "ok"}
    assert rec.context["dropped_keys"] == ["contact", "reason"]
    assert not EMAIL.search(stored_text(e))


def test_an_email_nested_deep_or_inside_a_list_is_dropped_and_the_rest_kept():
    org = str(uuid.uuid4())
    e = event(
        "billing.invoice.issued",
        org,
        {
            "organisation_id": org,
            "invoice_id": "inv-1",
            "recipients": ["finance@school.example", "ledger-team"],
            "billing": {"contact": {"primary": "x@y.example", "phone": "+91 99999 00000"}, "currency": "INR"},
        },
    )
    deliver(e)
    (rec,) = records(org)
    assert rec.after == {
        "organisation_id": org,
        "invoice_id": "inv-1",
        "recipients": ["ledger-team"],
        "billing": {"contact": {}, "currency": "INR"},
    }
    assert not EMAIL.search(stored_text(e)) and "99999" not in stored_text(e)


def test_ordinary_fields_are_not_over_stripped():
    """The filter must not eat what an audit trail is for: ids, names of things, statuses, amounts, dates."""
    org = str(uuid.uuid4())
    payload = {
        "organisation_id": org,
        "request_id": "r-9",
        "status": "approved",
        "mode": "cash",
        "amount": "1500.00",
        "decided_at": "2026-11-02T09:30:00+00:00",
        "slug": "harmony",
    }
    deliver(event("workflow.request.approved", org, dict(payload)))
    (rec,) = records(org)
    assert rec.after == payload
    assert "dropped_keys" not in rec.context


@pytest.mark.parametrize("name", consumers.AUDITED)
def test_no_audited_event_can_put_an_email_address_into_a_record(name):
    """Every event audit subscribes to, with an address under a contact key, under an innocent key and in free text:
    none of the three reaches the stored record. Keeps the next event added to AUDITED honest as well."""
    org = str(uuid.uuid4())
    e = event(
        name,
        org,
        {
            "organisation_id": org,
            "admin_email": "one@example.com",
            "label": "two@example.com",
            "reason": "please write to three@example.com about it",
            "kept": "visible",
        },
    )
    deliver(e)
    text = stored_text(e)
    assert not EMAIL.search(text), name
    if name != "tenancy.organisation.purged":
        # The over-stripping guard: harmless fields survive. Not for a purge: the organisation's trail is tombstoned
        # by design (#451, DPDP erasure keeps who-did-what but not the payloads), so nothing is left to be visible.
        assert "visible" in text, name


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
