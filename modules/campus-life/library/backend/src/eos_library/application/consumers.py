"""Handlers for the events library consumes (module.yaml consumes_events). Agreed with fees-accounts on #175: when an
organisation invoices library fines, fees-accounts publishes fees-accounts.invoice.paid with source_module "library"
and source_reference the fine id, and library marks that fine paid.

The event-bus relay finds CONSUMERS through the `eos.event_consumers` entry point (backend/pyproject.toml); a host
without the relay can call handle(db, name, payload) directly. Every handler is idempotent: a repeated event changes
nothing and answers why. Each runs in the event's organisation scope and commits on its own."""

from __future__ import annotations

from eos_core.tenant import is_bypass, organisation_scope
from sqlalchemy.orm import Session

from . import service

INVOICE_PAID = "fees-accounts.invoice.paid"


def _ignored(reason: str) -> dict:
    return {"result": "ignored", "reason": reason}


def on_invoice_paid(db: Session, payload: dict) -> dict:
    if payload.get("source_module") != "library":
        return _ignored("the invoice was not raised for a library fine")
    fine_id, invoice_id = payload["source_reference"], payload["invoice_id"]
    if not isinstance(fine_id, str) or not isinstance(invoice_id, str):
        return _ignored("source_reference and invoice_id must be strings")
    outcome = service.fine_paid_through_fees(db, fine_id, invoice_id)
    return {"result": "applied" if outcome == "marked paid" else "ignored", "reason": outcome}


HANDLERS = {INVOICE_PAID: on_invoice_paid}


def handle(db: Session, name: str, payload: dict, organisation_id: str | None = None) -> dict:
    """Apply one consumed event. Unknown names are ignored, so the host can relay every event. The envelope's
    organisation_id, when the relay passes it, wins over the payload's."""
    handler = HANDLERS.get(name)
    if handler is None:
        return _ignored(f"library does not consume {name}")
    org = organisation_id or payload.get("organisation_id")
    if not org:
        return _ignored("the event carries no organisation_id")
    if is_bypass():
        # organisation_scope does not lift platform_scope's bypass, so scoped queries would see every organisation.
        raise RuntimeError("consumers.handle must not run inside platform_scope")
    db.rollback()  # a fresh transaction, so Postgres row-level security is set for this event's organisation
    with organisation_scope(org):
        try:
            return handler(db, payload)
        except (KeyError, TypeError, ValueError) as e:
            db.rollback()  # a malformed payload is ignored with its reason, never left for the relay to retry
            return _ignored(f"malformed payload: {type(e).__name__}: {e}")
        finally:
            db.rollback()  # nothing left open: the next event starts in its own scope


def _relay(db: Session, event) -> None:
    """The event-bus relay's handler signature: (db, event) with event.name and event.payload."""
    handle(db, event.name, dict(event.payload or {}), getattr(event, "organisation_id", None))


CONSUMERS = {INVOICE_PAID: _relay}
