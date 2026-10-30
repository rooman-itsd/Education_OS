"""athlete-performance's athlete events link a user to an athlete; the handlers are idempotent, ignore stale
deliveries and are tenant-bound."""

from datetime import timedelta
from pathlib import Path

import yaml
from conftest import ATHLETE, BASE, NOW, Event, deliver
from eos_core.db import SessionLocal, new_id
from eos_tournament_events.application import consumers
from eos_tournament_events.infrastructure.models import AthleteLink
from sqlalchemy import select

ATHLETE_A = "11111111-1111-1111-1111-111111111111"


def _links(organisation_id: str) -> list[AthleteLink]:
    with SessionLocal() as db:
        return list(db.scalars(select(AthleteLink).where(AthleteLink.organisation_id == organisation_id)))


def _registered(org_id: str, user_id: str, at=NOW) -> Event:
    return Event(org_id, {"organisation_id": org_id, "athlete_id": ATHLETE_A, "user_id": user_id}, occurred_at=at)


def _updated(org_id: str, user_id: str | None, at, changed=("user_id",)) -> Event:
    payload = {"organisation_id": org_id, "athlete_id": ATHLETE_A, "changed_fields": list(changed), "status": "active"}
    if user_id:
        payload["user_id"] = user_id
    return Event(org_id, payload, name=consumers.ATHLETE_UPDATED, occurred_at=at)


def test_registration_links_the_user_once(client, org):
    user = new_id()
    event = _registered(org.id, user)
    deliver(event)
    deliver(event)  # at-least-once delivery
    [link] = _links(org.id)
    assert (link.athlete_id, link.user_id, link.event_id) == (ATHLETE_A, user, event.id)


def test_a_user_change_moves_the_link_and_a_late_older_event_does_not(client, org):
    first, second = new_id(), new_id()
    deliver(_registered(org.id, first))
    deliver(_updated(org.id, second, NOW + timedelta(minutes=5)))
    [link] = _links(org.id)
    assert link.user_id == second

    # a retry of the registration arriving late does not move the link back
    deliver(_registered(org.id, first))
    assert _links(org.id)[0].user_id == second
    # an update that does not touch the user is ignored
    deliver(_updated(org.id, first, NOW + timedelta(minutes=10), changed=("squad",)))
    assert _links(org.id)[0].user_id == second
    # user_id absent from an update that names it: the user was removed
    deliver(_updated(org.id, None, NOW + timedelta(minutes=15)))
    [link] = _links(org.id)
    assert link.user_id is None
    deliver(_updated(org.id, second, NOW + timedelta(minutes=12)))  # older than the removal
    assert _links(org.id)[0].user_id is None


def test_an_update_delivered_before_the_registration_wins(client, org):
    user = new_id()
    deliver(_updated(org.id, user, NOW + timedelta(minutes=1)))
    deliver(_registered(org.id, new_id()))
    assert _links(org.id)[0].user_id == user


def test_events_without_an_athlete_or_organisation_are_ignored(client, org):
    deliver(Event(org.id, {"organisation_id": org.id}))
    deliver(Event(None, {"athlete_id": ATHLETE_A, "user_id": new_id()}))
    payload = {"athlete_id": ATHLETE_A, "user_id": new_id(), "changed_fields": ["user_id"]}
    deliver(Event(None, payload, name=consumers.ATHLETE_UPDATED))
    assert _links(org.id) == []


def test_a_link_belongs_to_its_organisation(client, org, other_org):
    user = new_id()
    org.link(ATHLETE_A, user)
    tournaments = {}
    for o in (org, other_org):  # the same athlete id in another organisation is someone else
        tournaments[o.id] = o.tournament()["id"]
        o.entry(tournaments[o.id], [ATHLETE_A])
    _, as_athlete_elsewhere = other_org.user(ATHLETE, user_id=user)
    url = f"{BASE}/tournaments/{tournaments[other_org.id]}/entries"
    assert client.get(url, headers=as_athlete_elsewhere).json()["total"] == 0
    _, as_athlete = org.user(ATHLETE, user_id=user)
    url = f"{BASE}/tournaments/{tournaments[org.id]}/entries"
    assert client.get(url, headers=as_athlete).json()["total"] == 1


def test_the_consumers_are_the_events_module_yaml_declares():
    manifest = yaml.safe_load((Path(__file__).resolve().parents[2] / "module.yaml").read_text(encoding="utf-8"))
    assert set(manifest["consumes_events"]) == set(consumers.CONSUMERS)
