"""What audit records from other modules' events (event-bus entry point `eos.event_consumers`).

The audit store is fed by the outbox: every state change listed in AUDITED becomes one append-only record in the
event's organisation, with the event's actor, time and payload. Super admin actions (SUPER_ADMIN_ACTIONS) also get
a platform-level record (organisation_id null), which is what `audit.super-admin-actions` and a super admin's
cross-organisation search read.

Idempotent: a record's client_token is derived from the event id (`event:<id>`, and `event:<id>:platform` for the
platform copy), so a redelivered event — delivery is at-least-once — appends nothing. A payload key the audit
contract refuses (anything that looks like a password, secret or token) is dropped, and the dropped key names are
kept in the record's context, so a record still says that it changed. Any other failure raises, so the relay
retries the event and finally dead-letters it, where an operator sees it: a lost audit record must never pass
silently.

The list is explicit (ADR-0003: a consumer declares what it subscribes to). A module that adds a state-changing
event adds it here and to contracts/events.yaml `consumes`."""

from __future__ import annotations

import logging

from eos_core import events
from eos_core.db import SessionLocal
from eos_core.tenant import platform_scope
from sqlalchemy.orm import Session

from . import service
from .jobs import PRUNE

log = logging.getLogger("eos.audit")

AUDITED: tuple[str, ...] = (
    # tenancy: an organisation's lifecycle and every super admin operation on it
    "tenancy.organisation.registered",
    "tenancy.organisation.verified",
    "tenancy.package.requested",
    "tenancy.organisation.approved",
    "tenancy.package.changed",
    "tenancy.organisation.activated",
    "tenancy.organisation.suspended",
    "tenancy.organisation.archived",
    "tenancy.organisation.exported",
    "tenancy.organisation.deletion_requested",
    "tenancy.organisation.restored",
    "tenancy.organisation.purged",
    "tenancy.entitlement.changed",
    "tenancy.impersonation.started",
    # identity
    "identity.user.created",
    "identity.user.oidc_linked",
    # billing: subscription and invoice state (not the reminders, which change nothing)
    "billing.subscription.started",
    "billing.subscription.upgraded",
    "billing.subscription.downgraded",
    "billing.subscription.expired",
    "billing.trial.expired",
    "billing.invoice.issued",
    "billing.invoice.paid",
    # workflow decisions
    "workflow.request.submitted",
    "workflow.step.advanced",
    "workflow.request.approved",
    "workflow.request.rejected",
    "workflow.request.delegated",
    # documents
    "documents.document.uploaded",
    "documents.document.deleted",
    # reporting: who ran and exported which report
    "reporting.report.executed",
    "reporting.report.exported",
)

# Operations only a super admin (or the platform acting for one) performs on an organisation.
SUPER_ADMIN_ACTIONS = frozenset(
    {
        "tenancy.organisation.approved",
        "tenancy.package.changed",
        "tenancy.organisation.suspended",
        "tenancy.organisation.archived",
        "tenancy.organisation.exported",
        "tenancy.organisation.deletion_requested",
        "tenancy.organisation.restored",
        "tenancy.organisation.purged",
        "tenancy.impersonation.started",
    }
)


def _without_secrets(payload: dict) -> tuple[dict, list[str]]:
    """The payload minus any key the audit contract refuses to store (at any depth), and the names dropped."""
    dropped: list[str] = []

    def clean(value):
        if isinstance(value, dict):
            out = {}
            for key, inner in value.items():
                if service.SECRET_KEY_RE.search(str(key)):
                    dropped.append(str(key))
                    continue
                out[key] = clean(inner)
            return out
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value

    return clean(payload), dropped


def _entity(event_name: str, payload: dict, organisation_id: str | None) -> tuple[str, str]:
    """<module>.<entity>.<verb> -> (entity, the id the payload carries for it, else the organisation's)."""
    entity = event_name.split(".")[1]
    for key in (f"{entity}_id", "request_id", "document_id", "execution_id", "invoice_id", "user_id"):
        if payload.get(key):
            return entity, str(payload[key])
    return entity, str(payload.get("organisation_id") or organisation_id or "platform")


def on_event(db: Session, event) -> None:
    module, action = event.name.split(".", 1)
    payload, dropped = _without_secrets(dict(event.payload or {}))
    entity_type, entity_id = _entity(event.name, payload, event.organisation_id)
    context = {"source": "event-bus", "event_id": event.id, "event_version": getattr(event, "version", 1)}
    if dropped:
        context["dropped_keys"] = sorted(set(dropped))
    occurred_at = getattr(event, "occurred_at", None)

    def write(session: Session, organisation_id: str | None, token: str) -> None:
        service.record(
            session,
            organisation_id=organisation_id,
            actor=event.actor,
            module=module,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            after=payload or None,
            context={**context, "organisation_id": event.organisation_id} if organisation_id is None else context,
            client_token=token,
            occurred_at=occurred_at,
        )

    if not event.organisation_id:
        write(db, None, f"event:{event.id}")  # a platform event: the relay's session is already in platform scope
        return
    if event.name in SUPER_ADMIN_ACTIONS:
        # The platform copy needs a transaction that BEGINS in platform scope: on PostgreSQL row-level security is
        # set when a transaction begins, so the relay's session (in the event's organisation) cannot write a row
        # without one. Committed first and on its own; both records are idempotent on their client_token, so a
        # retry after the organisation's record fails records nothing twice.
        with platform_scope(), SessionLocal() as platform_db:
            write(platform_db, None, f"event:{event.id}:platform")
            platform_db.commit()
    write(db, event.organisation_id, f"event:{event.id}")


def on_job_due(db: Session, event) -> None:
    """scheduler.job.due for audit.prune: prune and report audit.job.finished, which closes the scheduler's run.
    A failed prune is reported, not raised: the next day's run tries again."""
    payload = event.payload or {}
    if payload.get("job") != PRUNE:
        return
    try:
        removed = service.prune(db)
        outcome, detail = "succeeded", f"{removed} record(s) removed"
    except Exception as e:  # noqa: BLE001  reported to the run
        db.rollback()
        log.exception("audit.prune failed")
        outcome, detail = "failed", type(e).__name__
    events.publish(
        db,
        "audit.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": outcome, "detail": detail},
    )


def on_purged(db: Session, event) -> None:
    """tenancy.organisation.purged: record it like any audited event (a platform-level record, which keeps no
    organisation_id and so is not redacted), then tombstone the purged organisation's trail. Redelivery is safe:
    the record is idempotent on the event id, and a tombstone is not redacted twice."""
    on_event(db, event)
    organisation_id = (event.payload or {}).get("organisation_id")
    if organisation_id:
        count = service.redact_organisation(db, str(organisation_id))
        log.info("redacted %s audit record(s) of purged organisation %s", count, organisation_id)


CONSUMERS = {
    **dict.fromkeys(AUDITED, on_event),
    "tenancy.organisation.purged": on_purged,
    "scheduler.job.due": on_job_due,
}
