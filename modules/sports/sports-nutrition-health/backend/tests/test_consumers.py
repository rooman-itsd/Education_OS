"""athlete-performance.athlete.registered links a user to an athlete; the handler is idempotent and tenant-bound."""

from conftest import ATHLETE, BASE, Event, deliver
from eos_core.db import SessionLocal, new_id
from eos_sports_nutrition_health.infrastructure.models import AthleteLink
from sqlalchemy import select

ATHLETE_A = "11111111-1111-1111-1111-111111111111"


def _links(organisation_id: str) -> list[AthleteLink]:
    with SessionLocal() as db:
        return list(db.scalars(select(AthleteLink).where(AthleteLink.organisation_id == organisation_id)))


def test_registration_links_the_user_once(client, org):
    user = new_id()
    event = Event(org.id, {"organisation_id": org.id, "athlete_id": ATHLETE_A, "user_id": user})
    deliver(event)
    deliver(event)  # at-least-once delivery
    [link] = _links(org.id)
    assert (link.athlete_id, link.user_id, link.event_id) == (ATHLETE_A, user, event.id)

    other = new_id()
    deliver(Event(org.id, {"organisation_id": org.id, "athlete_id": ATHLETE_A, "user_id": other}))
    [link] = _links(org.id)
    assert link.user_id == other


def test_events_without_a_user_or_organisation_are_ignored(client, org):
    deliver(Event(org.id, {"organisation_id": org.id, "athlete_id": ATHLETE_A}))
    deliver(Event(None, {"athlete_id": ATHLETE_A, "user_id": new_id()}))
    assert _links(org.id) == []


def test_a_link_belongs_to_its_organisation(client, org, other_org):
    user = new_id()
    org.link(ATHLETE_A, user)
    org.plan(ATHLETE_A)
    other_org.plan(ATHLETE_A)  # the same athlete id in another organisation is someone else
    _, as_athlete_elsewhere = other_org.user(ATHLETE, user_id=user)
    assert client.get(f"{BASE}/nutrition-plans", headers=as_athlete_elsewhere).json()["total"] == 0
    _, as_athlete = org.user(ATHLETE, user_id=user)
    assert client.get(f"{BASE}/nutrition-plans", headers=as_athlete).json()["total"] == 1
