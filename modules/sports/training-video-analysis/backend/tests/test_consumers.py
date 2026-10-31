"""athlete-performance's athlete events link a user to an athlete; the handlers are idempotent and tenant-bound."""

from datetime import timedelta

from conftest import ATHLETE, BASE, Event, deliver
from eos_core.db import SessionLocal, new_id
from eos_training_video_analysis.application import consumers
from eos_training_video_analysis.infrastructure.models import AthleteLink
from sqlalchemy import select

ATHLETE_A = "11111111-1111-1111-1111-111111111111"


def _links(organisation_id: str) -> list[AthleteLink]:
    with SessionLocal() as db:
        return list(db.scalars(select(AthleteLink).where(AthleteLink.organisation_id == organisation_id)))


def _registered(org_id: str, user_id: str | None, **kw) -> Event:
    payload = {"organisation_id": org_id, "athlete_id": ATHLETE_A}
    if user_id:
        payload["user_id"] = user_id
    return Event(org_id, payload, **kw)


def _updated(org_id: str, payload: dict, **kw) -> Event:
    body = {"organisation_id": org_id, "athlete_id": ATHLETE_A, "status": "active", **payload}
    return Event(org_id, body, name=consumers.ATHLETE_UPDATED, **kw)


def test_registration_links_the_user_once(client, org):
    user = new_id()
    event = _registered(org.id, user)
    deliver(event)
    deliver(event)  # at-least-once delivery
    [link] = _links(org.id)
    assert (link.athlete_id, link.user_id, link.event_id) == (ATHLETE_A, user, event.id)

    # a retry of an older event arriving late does not move the link back
    deliver(_registered(org.id, new_id(), occurred_at=event.occurred_at - timedelta(minutes=5)))
    [link] = _links(org.id)
    assert link.user_id == user


def test_a_user_change_moves_the_link_and_a_removal_clears_it(client, org):
    first, second = new_id(), new_id()
    registered = _registered(org.id, first)
    deliver(registered)
    t = registered.occurred_at

    # an update that does not change the user is ignored, even with a user_id in the payload
    deliver(_updated(org.id, {"user_id": second, "changed_fields": ["squad"]}, occurred_at=t + timedelta(minutes=1)))
    assert _links(org.id)[0].user_id == first

    moved = _updated(org.id, {"user_id": second, "changed_fields": ["user_id"]}, occurred_at=t + timedelta(minutes=2))
    deliver(moved)
    deliver(moved)
    assert _links(org.id)[0].user_id == second

    # user_id absent while changed_fields names it: the athlete has no user any more
    org.session(attendee_ids=[ATHLETE_A])
    _, as_second = org.user(ATHLETE, user_id=second)
    assert org.get("/sessions", as_second).json()["total"] == 1
    deliver(_updated(org.id, {"changed_fields": ["user_id"]}, occurred_at=t + timedelta(minutes=3)))
    [link] = _links(org.id)
    assert link.user_id is None
    assert org.get("/sessions", as_second).json()["total"] == 0

    # the late registration retry does not bring the old user back
    deliver(registered)
    assert _links(org.id)[0].user_id is None


def test_a_removal_that_arrives_first_still_wins_by_time(client, org):
    removed = _updated(org.id, {"changed_fields": ["user_id"]})
    deliver(removed)
    deliver(_registered(org.id, new_id(), occurred_at=removed.occurred_at - timedelta(minutes=1)))
    assert _links(org.id)[0].user_id is None


def test_events_without_a_user_or_organisation_are_ignored(client, org):
    deliver(_registered(org.id, None))
    deliver(Event(None, {"athlete_id": ATHLETE_A, "user_id": new_id()}))
    deliver(Event(None, {"athlete_id": ATHLETE_A, "changed_fields": ["user_id"]}, name=consumers.ATHLETE_UPDATED))
    assert _links(org.id) == []


def test_a_link_belongs_to_its_organisation(client, org, other_org):
    user = new_id()
    org.link(ATHLETE_A, user)
    org.session(attendee_ids=[ATHLETE_A])
    other_org.session(attendee_ids=[ATHLETE_A])  # the same athlete id in another organisation is someone else
    _, as_athlete_elsewhere = other_org.user(ATHLETE, user_id=user)
    assert client.get(f"{BASE}/sessions", headers=as_athlete_elsewhere).json()["total"] == 0
    _, as_athlete = org.user(ATHLETE, user_id=user)
    assert client.get(f"{BASE}/sessions", headers=as_athlete).json()["total"] == 1
