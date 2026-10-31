"""Events this module consumes (module.yaml consumes_events), registered with the event bus on the
`eos.event_consumers` entry point in backend/pyproject.toml. The bus calls each handler in its own transaction, in
the event's organisation, and commits it; delivery is at-least-once, so every handler is idempotent.

Both keep AthleteLink, which user is which athlete, so an athlete sees only their own sessions and videos. The event
is read by attribute (id, organisation_id, occurred_at, payload), so this module does not import the event bus."""

from __future__ import annotations

from sqlalchemy.orm import Session

from ..infrastructure import repository as repo
from ..infrastructure.models import AthleteLink, as_utc

ATHLETE_REGISTERED = "athlete-performance.athlete.registered"
ATHLETE_UPDATED = "athlete-performance.athlete.updated"


def _link(db: Session, event, athlete_id: str, user_id: str | None) -> None:
    """Point the athlete at user_id (None: no user). A repeat delivery changes nothing; only an event newer than the
    one that set the link moves it, so a retry of an older event arriving late does not move it back."""
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
        link.user_id, link.event_id, link.linked_at = user_id, event.id, occurred_at
    db.flush()


def on_athlete_registered(db: Session, event) -> None:
    """An athlete without a user_id cannot sign in and needs no link."""
    payload = event.payload or {}
    athlete_id, user_id = payload.get("athlete_id"), payload.get("user_id")
    if not event.organisation_id or not athlete_id or not user_id:
        return
    _link(db, event, athlete_id, user_id)


def on_athlete_updated(db: Session, event) -> None:
    """Only a change of the athlete's user matters here (changed_fields names user_id). The new user_id is in the
    payload; its absence means the athlete no longer has a user, and the link is cleared."""
    payload = event.payload or {}
    athlete_id = payload.get("athlete_id")
    if not event.organisation_id or not athlete_id or "user_id" not in (payload.get("changed_fields") or []):
        return
    _link(db, event, athlete_id, payload.get("user_id"))


CONSUMERS = {ATHLETE_REGISTERED: on_athlete_registered, ATHLETE_UPDATED: on_athlete_updated}
