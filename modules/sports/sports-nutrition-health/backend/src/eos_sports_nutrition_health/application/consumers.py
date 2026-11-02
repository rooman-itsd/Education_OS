"""Events this module consumes (module.yaml consumes_events), registered with the event bus on the
`eos.event_consumers` entry point in backend/pyproject.toml. The bus calls each handler in its own transaction, in
the event's organisation, and commits it; delivery is at-least-once, so every handler is idempotent.

The event is read by attribute (id, organisation_id, payload), so this module does not import the event bus."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.models import AthleteLink, as_utc

ATHLETE_REGISTERED = "athlete-performance.athlete.registered"


def on_athlete_registered(db: Session, event) -> None:
    """Remember which user is which athlete, so an athlete sees only their own rows. An athlete without a user_id
    cannot sign in and needs no link. A repeat delivery changes nothing; a newer registration of the same athlete moves
    the link, an older one arriving late does not."""
    payload = event.payload or {}
    athlete_id, user_id = payload.get("athlete_id"), payload.get("user_id")
    if not event.organisation_id or not athlete_id or not user_id:
        return
    db.info["organisation_id"] = event.organisation_id
    occurred_at = as_utc(event.occurred_at)
    link = repo.link_of(db, athlete_id)
    if link is None:
        db.add(
            AthleteLink(
                organisation_id=event.organisation_id,
                athlete_id=athlete_id,
                user_id=user_id,
                event_id=event.id,
                linked_at=occurred_at,
            )
        )
    elif link.event_id != event.id and occurred_at > as_utc(link.linked_at):
        # Delivery is at-least-once and a retry can arrive late: only a newer event moves the link.
        link.user_id, link.event_id, link.linked_at = user_id, event.id, occurred_at
    db.flush()


CONSUMERS = {ATHLETE_REGISTERED: on_athlete_registered}
