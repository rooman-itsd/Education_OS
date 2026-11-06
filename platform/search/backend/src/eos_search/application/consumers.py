"""What search reacts to (event-bus entry point `eos.event_consumers`).

- the trigger events modules declared in contracts/searchable.yaml (plus the first modules' events, which are listed
  here so the consumer is registered before their provider is installed): index or delete a document;
- tenancy.entitlement.changed: keep search's copy of the organisation's modules, so a switched-off module stops
  appearing in results on the next request;
- tenancy.organisation.purged: remove every document of the organisation.

Handlers run in their own session in the event's organisation (platform scope for the purge, whose envelope has no
organisation) and are idempotent on the event."""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from eos_core import events
from sqlalchemy.orm import Session

from ..domain.documents import valid_uuid
from ..infrastructure.engine import get_engine
from . import indexer, state
from .registry import get_registry

log = logging.getLogger("eos.search")

FIRST_MODULE_EVENTS = (
    "student-information.person.created",
    "student-information.person.updated",
    "student-information.person.status-changed",
    "academic-management.course.created",
    "academic-management.course.updated",
    "academic-management.course.archived",
    "knowledge-base.article.published",
    "knowledge-base.article.archived",
)


def on_trigger(db: Session, event) -> None:
    indexer.index_event(db, event)


def on_entitlement_changed(db: Session, event) -> None:
    if not event.organisation_id:
        return
    state.set_entitlement(db, str(event.organisation_id), (event.payload or {}).get("modules"))


def on_purged(db: Session, event) -> None:
    """The envelope's organisation_id is null (the tenant no longer exists), so this is the one place the id comes
    from the payload. It is checked to be a uuid, and nothing is indexed from it."""
    organisation_id = (event.payload or {}).get("organisation_id")
    if not valid_uuid(organisation_id):
        log.warning("search: tenancy.organisation.purged without a usable organisation_id")
        return
    organisation_id = str(organisation_id)
    deleted = get_engine().delete_by_organisation(organisation_id)  # raises on an outage: the relay retries
    state.forget_organisation(db, organisation_id)
    events.publish(
        db,
        "search.organisation.purged",
        None,
        {
            "organisation_id": organisation_id,
            "documents_deleted": deleted,
            "purged_at": datetime.now(UTC).isoformat(),
        },
    )


def build_consumers() -> dict:
    names = set(FIRST_MODULE_EVENTS) | get_registry().trigger_events()
    return {
        **dict.fromkeys(sorted(names), on_trigger),
        "tenancy.entitlement.changed": on_entitlement_changed,
        "tenancy.organisation.purged": on_purged,
    }


CONSUMERS = build_consumers()
