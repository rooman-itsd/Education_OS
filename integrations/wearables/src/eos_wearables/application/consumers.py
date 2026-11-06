"""Events this module consumes (module.yaml consumes_events), registered with the event bus on the `eos.event_consumers`
entry point in pyproject.toml. The bus calls each handler in its own transaction, in the event's organisation, and commits
it; delivery is at-least-once, so the handler is idempotent. The event is read by attribute, so this module does not import
the event bus."""

from __future__ import annotations

from eos_core.db import scoped
from eos_core.tenant import organisation_scope
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from ..infrastructure.models import AuditEntry, LinkState, Record
from ..infrastructure.providers.base import utcnow

ACCOUNT_LINK_REVOKED = "integration-hub.account-link.revoked"
PORT = "wearable-data"


def on_account_link_revoked(db: Session, event) -> None:
    """Delete every record collected under the link at once, and mark it revoked. A repeat delivery changes nothing, and an
    event for another port's link (a document wallet) is none of ours."""
    payload = event.payload or {}
    link_id, org = payload.get("account_link_id"), event.organisation_id or payload.get("organisation_id")
    if payload.get("port") != PORT or not link_id or not org:
        return
    db.info["organisation_id"] = org
    with organisation_scope(org):
        row = db.scalar(scoped(db, select(LinkState).where(LinkState.account_link_id == str(link_id)), LinkState))
        if row is None:
            return
        db.execute(delete(Record).where(Record.account_link_id == str(link_id), Record.organisation_id == org))
        if row.status != "revoked":
            row.status, row.status_since = "revoked", utcnow()
            db.add(
                AuditEntry(
                    organisation_id=org,
                    actor=None,
                    action="link.revoked",
                    entity="link",
                    entity_id=str(link_id),
                    occurred_at=utcnow(),
                )
            )
        row.last_data_at = row.last_synced_at = None
        db.flush()


CONSUMERS = {ACCOUNT_LINK_REVOKED: on_account_link_revoked}
