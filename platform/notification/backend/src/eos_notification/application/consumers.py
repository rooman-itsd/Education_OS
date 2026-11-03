"""What notification sends in reaction to other modules' events (event-bus entry point `eos.event_consumers`).

This is the half that makes the outbox worth draining: billing raises `billing.trial.expiring`, the relay hands
it here, and the organisation's admins get the email. Without it the relay delivers to nobody and marks the
event published, which looks healthy and sends nothing.

Each handler runs in its own session, already in the event's organisation (the relay's contract), and sends one
message per admin through `send_message`, which owns that session's transaction. The `client_token` is derived
from the event id and the recipient (or, for trial reminders, the reminder_key and the recipient), so a
redelivered event — delivery is at-least-once — returns the original message untouched and mails nobody twice.

Failures:
- A provider failure does NOT raise. A retryable one leaves the message queued with `next_attempt_at`; the
  scheduled `notification.recover-stuck` job (see jobs.py, on_job_due) sends it again, with bounded attempts and
  backoff. A permanent one marks it failed and publishes notification.message.failed.
- Anything that stops the handler before a message is accepted (the organisation name cannot be looked up, the
  database is unavailable) raises, so the relay retries the event with backoff and finally dead-letters it,
  which an operator sees. Returning would mark the event done and lose the email silently.
- An organisation with no active admin is logged and skipped: retrying cannot change that."""

from __future__ import annotations

import logging
from collections.abc import Callable

from eos_core import events
from eos_identity.application.service import list_users
from sqlalchemy.orm import Session

from . import messages
from .jobs import RECOVER_STUCK
from .organisations import hooks

log = logging.getLogger("eos.notification")

ADMIN_ROLE = "org-admin"
CHANNEL = "email"

# event name -> (template key, how its payload becomes the template's variables beyond organisation_name)
Variables = Callable[[dict], dict]
EVENTS: dict[str, tuple[str, Variables]] = {
    "tenancy.organisation.verified": ("tenancy.organisation.verified", lambda p: {}),
    "tenancy.organisation.approved": ("tenancy.organisation.approved", lambda p: {}),
    "billing.trial.expiring": (
        "billing.trial.reminder",
        lambda p: {"trial_ends_on": str(p.get("trial_ends_on", "")), "days_left": str(p.get("days_left", ""))},
    ),
    "billing.trial.expired": ("billing.trial.expired", lambda p: {}),
}
# Not wired: billing.invoice.issued. Its template needs invoice_number and due_on, which the event's payload
# (organisation_id, invoice_id, amount, currency) does not carry. Billing's contract has to say them first.


def admins(db: Session, organisation_id: str) -> list:
    """The organisation's admins, in identity. list_users is tenant-scoped, and the relay has already put this
    session in the event's organisation, so this never sees another tenant's users."""
    return [u for u in list_users(db) if ADMIN_ROLE in (u.roles or []) and u.status == "active"]


def on_event(db: Session, event) -> None:
    mapping = EVENTS.get(event.name)
    if mapping is None or not event.organisation_id:
        return
    template, variables_of = mapping
    _send_to_admins(db, event, template, variables_of(event.payload or {}))


# --- an organisation's status changed (tenancy.organisation.archived | suspended | activated) ---------------------
# One handler, because one event can mean different things: tenancy refuses a registration by archiving (or
# suspending) an organisation that is still pending, and closes or suspends an active one the same way. The payload's
# previous_status (tenancy contract 0.3.0) tells them apart. Without it nothing is sent: guessing would mail a
# rejection to an organisation that was closed, or the reverse.
REFUSED_FROM = frozenset({"pending_verification", "pending_approval"})
OFF_STATUSES = frozenset({"suspended", "archived"})
STATUS_EVENTS = ("tenancy.organisation.archived", "tenancy.organisation.suspended", "tenancy.organisation.activated")


def status_template(event) -> tuple[str, dict] | None:
    """(template, variables) for a status-change event, or None when it calls for no email.

    archived with delete_after         a deletion request: data kept until delete_after   -> deletion_scheduled
    archived | suspended, from pending  a refused registration                             -> rejected
    suspended, from active              suspended by the platform operator                 -> suspended
    archived, from active               closed by the platform operator                    -> closed
    activated, from suspended|archived  back in service                                    -> reactivated
    Anything else (a first activation after approval, which `approved` already mails; no previous_status) -> None."""
    payload = event.payload or {}
    previous = payload.get("previous_status")
    reason = str(payload.get("reason") or "not given")
    if event.name == "tenancy.organisation.archived" and payload.get("delete_after"):
        return "tenancy.organisation.deletion_scheduled", {
            "reason": reason,
            "delete_on": str(payload["delete_after"])[:10],
        }
    if event.name in ("tenancy.organisation.archived", "tenancy.organisation.suspended") and previous in REFUSED_FROM:
        return "tenancy.organisation.rejected", {"reason": reason}
    if event.name == "tenancy.organisation.suspended" and previous == "active":
        return "tenancy.organisation.suspended", {"reason": reason}
    if event.name == "tenancy.organisation.archived" and previous == "active":
        return "tenancy.organisation.closed", {"reason": reason}
    if event.name == "tenancy.organisation.activated" and previous in OFF_STATUSES:
        return "tenancy.organisation.reactivated", {}
    return None


def on_status_changed(db: Session, event) -> None:
    if not event.organisation_id:
        return
    chosen = status_template(event)
    if chosen is None:
        return
    template, variables = chosen
    _send_to_admins(db, event, template, variables)


def _send_to_admins(db: Session, event, template: str, extra: dict) -> None:
    organisation_name = hooks.name(db, event.organisation_id)
    if not organisation_name:
        # Unwired host (tenancy's entry point missing from this process), or an organisation that no longer
        # exists. Raise so the relay retries and, if it never resolves, dead-letters the event where an operator
        # sees it. Returning marked the event done and lost the email; sending would read "The trial for  has
        # ended".
        raise LookupError(f"no organisation name for {event.organisation_id}: {template} not sent")
    recipients = admins(db, event.organisation_id)
    if not recipients:
        log.warning("organisation %s has no active admin: %s not sent", event.organisation_id, template)
        return
    payload = event.payload or {}
    variables = {"organisation_name": organisation_name, **extra}
    reminder_key = payload.get("reminder_key")
    for user in recipients:
        token = f"reminder:{reminder_key}:{user.id}" if reminder_key else f"event:{event.id}:{user.id}"
        messages.send_message(
            db,
            template=template,
            channel=CHANNEL,
            recipient={"user_id": user.id},
            variables=variables,
            client_token=token,
        )


def on_job_due(db: Session, event) -> None:
    """scheduler.job.due for notification's own job: run the recovery sweep and report the outcome, which closes
    the scheduler's run. The sweep uses sessions of its own per message (it crosses organisations to list them),
    so this session only carries the finished event. A failed sweep is reported, not raised: the next tick runs
    it again, and redelivering the due event would only repeat the same sweep."""
    payload = event.payload or {}
    if payload.get("job") != RECOVER_STUCK:
        return  # another module's job
    try:
        counts = messages.recover_stuck()
        outcome = "succeeded"
        detail = ", ".join(f"{k} {v}" for k, v in counts.items())
    except Exception as e:  # noqa: BLE001  reported to the run; exception text may carry addresses
        log.exception("notification.recover-stuck failed")
        outcome, detail = "failed", type(e).__name__
    events.publish(
        db,
        "notification.job.finished",
        event.organisation_id,
        {"run_id": payload.get("run_id"), "outcome": outcome, "detail": detail},
    )


CONSUMERS = {
    **dict.fromkeys(EVENTS, on_event),
    **dict.fromkeys(STATUS_EVENTS, on_status_changed),
    "scheduler.job.due": on_job_due,
}
