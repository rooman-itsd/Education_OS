"""What notification sends in reaction to other modules' events (event-bus entry point `eos.event_consumers`).

This is the half that makes the outbox worth draining: billing raises `billing.trial.expiring`, the relay hands
it here, and the organisation's admins get the email. Without it the relay delivers to nobody and marks the
event published, which looks healthy and sends nothing.

Each handler runs in its own session, already in the event's organisation (the relay's contract), and sends one
message per admin through `send_message`, which owns that session's transaction. The `client_token` is derived
from the event id and the recipient, so a redelivered event — delivery is at-least-once — returns the original
message untouched and mails nobody twice. A send that fails raises, so the relay retries the whole event with
backoff; a recipient already sent to is deduplicated on the retry."""

from __future__ import annotations

import logging
from collections.abc import Callable

from eos_identity.application.service import list_users
from sqlalchemy.orm import Session

from . import messages
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
    organisation_name = hooks.name(db, event.organisation_id)
    if not organisation_name:
        # Unwired host, or an organisation that no longer exists. Loud, because the alternative is an email
        # that reads "The trial for  has ended".
        log.error("no organisation name for %s: %s not sent", event.organisation_id, template)
        return
    recipients = admins(db, event.organisation_id)
    if not recipients:
        log.warning("organisation %s has no active admin: %s not sent", event.organisation_id, template)
        return
    payload = event.payload or {}
    variables = {"organisation_name": organisation_name, **variables_of(payload)}
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


CONSUMERS = dict.fromkeys(EVENTS, on_event)
