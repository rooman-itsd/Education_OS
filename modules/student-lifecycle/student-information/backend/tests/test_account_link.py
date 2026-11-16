"""student-information.person.account-linked (contracts/events.yaml): the person-to-sign-in-account link.

Other modules key their data on person_id but resolve a student's own /me reads by the caller's identity user id; this
event is how they map one to the other. It is published whenever identity_user_id is set, changed or cleared, in the
transaction of the write, and republished on request (POST /account-links/republish) for links made before it existed.
"""

from __future__ import annotations

import pytest
from conftest import ADMISSIONS, BASE_PATH, READ_ONLY, REGISTRAR, make_auth_headers
from eos_core.db import new_id
from eos_core.events import OutboxEvent
from eos_student_information.application.service import (
    ACCOUNT_LINKED,
    Actor,
    ServiceError,
    create_person,
    republish_account_links,
    update_person,
)
from sqlalchemy import select

ALL_PERMISSIONS = {
    "student-information:person:read",
    "student-information:person:write",
    "student-information:status:manage",
    "student-information:document:manage",
    "student-information:id-card:manage",
}


def _actor(tag: str) -> Actor:
    return Actor(user_id=f"staff-{tag}", organisation_id=f"org-link-{tag}-{new_id()[:8]}", permissions=ALL_PERMISSIONS)


def _events(db, org_id: str, name: str = ACCOUNT_LINKED) -> list[OutboxEvent]:
    return list(
        db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.organisation_id == org_id, OutboxEvent.name == name)
            .order_by(OutboxEvent.occurred_at.asc(), OutboxEvent.id.asc())
        )
    )


def _payloads(db, org_id: str) -> list[dict]:
    return [e.payload for e in _events(db, org_id)]


def test_created_with_an_account_announces_the_link(db):
    actor = _actor("create")
    user = new_id()
    person = create_person(db, actor, {"first_name": "Asha", "last_name": "Rao", "identity_user_id": user})
    db.commit()

    created = _events(db, actor.organisation_id, "student-information.person.created")
    assert len(created) == 1 and created[0].payload["identity_user_id"] == user
    links = _events(db, actor.organisation_id)
    assert len(links) == 1
    assert links[0].payload == {
        "organisation_id": actor.organisation_id,
        "person_id": person.id,
        "identity_user_id": user,
        "linked": True,
        "previous_identity_user_id": None,
    }
    assert links[0].actor == actor.user_id


def test_created_without_an_account_announces_no_link(db):
    actor = _actor("nolink")
    create_person(db, actor, {"first_name": "No", "last_name": "Account"})
    db.commit()

    created = _events(db, actor.organisation_id, "student-information.person.created")
    assert created[0].payload["identity_user_id"] is None
    assert _payloads(db, actor.organisation_id) == []


def test_a_blank_account_is_no_account(db):
    actor = _actor("blank")
    person = create_person(db, actor, {"first_name": "Blank", "last_name": "User", "identity_user_id": "  "})
    db.commit()

    assert person.identity_user_id is None
    assert _payloads(db, actor.organisation_id) == []


def test_set_change_and_clear_each_announce_the_link(db):
    actor = _actor("lifecycle")
    person = create_person(db, actor, {"first_name": "Link", "last_name": "Later"})
    db.commit()
    first, second = new_id(), new_id()

    update_person(db, actor, person.id, {"identity_user_id": first})
    db.commit()
    update_person(db, actor, person.id, {"identity_user_id": second})
    db.commit()
    update_person(db, actor, person.id, {"identity_user_id": None})
    db.commit()

    assert [
        (p["identity_user_id"], p["linked"], p["previous_identity_user_id"])
        for p in _payloads(db, actor.organisation_id)
    ] == [(first, True, None), (second, True, first), (None, False, second)]


def test_clearing_with_a_blank_value_announces_the_unlink(db):
    actor = _actor("blankclear")
    user = new_id()
    person = create_person(db, actor, {"first_name": "Was", "last_name": "Linked", "identity_user_id": user})
    db.commit()

    update_person(db, actor, person.id, {"identity_user_id": ""})
    db.commit()

    assert person.identity_user_id is None
    last = _payloads(db, actor.organisation_id)[-1]
    assert (last["identity_user_id"], last["linked"], last["previous_identity_user_id"]) == (None, False, user)


def test_an_update_that_keeps_the_account_announces_no_link(db):
    actor = _actor("same")
    user = new_id()
    person = create_person(db, actor, {"first_name": "Same", "last_name": "User", "identity_user_id": user})
    db.commit()

    update_person(db, actor, person.id, {"identity_user_id": user})
    update_person(db, actor, person.id, {"preferred_name": "Sam"})
    db.commit()

    assert len(_payloads(db, actor.organisation_id)) == 1  # only the creation's


def test_a_refused_link_announces_nothing(db):
    """An account already linked to another person is a 409; the refused write publishes no event."""
    actor = _actor("dup")
    user = new_id()
    create_person(db, actor, {"first_name": "First", "last_name": "Holder", "identity_user_id": user})
    other = create_person(db, actor, {"first_name": "Second", "last_name": "Claimant"})
    db.commit()

    with pytest.raises(ServiceError) as err:
        update_person(db, actor, other.id, {"identity_user_id": user})
    assert err.value.code == "duplicate_identity_user"

    assert other.identity_user_id is None
    assert len(_payloads(db, actor.organisation_id)) == 1


def test_a_rolled_back_link_announces_nothing(db):
    actor = _actor("rollback")
    create_person(db, actor, {"first_name": "Roll", "last_name": "Back", "identity_user_id": new_id()})
    db.rollback()

    assert _payloads(db, actor.organisation_id) == []


def test_republish_announces_every_current_link_in_the_organisation_only(db):
    actor, other_org = _actor("republish"), _actor("republish-other")
    linked_a, linked_b = new_id(), new_id()
    a = create_person(db, actor, {"first_name": "A", "last_name": "Linked", "identity_user_id": linked_a})
    b = create_person(db, actor, {"first_name": "B", "last_name": "Linked"})
    create_person(db, actor, {"first_name": "C", "last_name": "Unlinked"})
    create_person(db, other_org, {"first_name": "D", "last_name": "Elsewhere", "identity_user_id": new_id()})
    db.commit()
    update_person(db, actor, b.id, {"identity_user_id": linked_b})
    db.commit()
    before = len(_payloads(db, actor.organisation_id))
    other_before = len(_payloads(db, other_org.organisation_id))

    assert republish_account_links(db, actor) == 2
    db.commit()

    again = _payloads(db, actor.organisation_id)[before:]
    assert {(p["person_id"], p["identity_user_id"], p["linked"], p["previous_identity_user_id"]) for p in again} == {
        (a.id, linked_a, True, None),
        (b.id, linked_b, True, None),
    }
    assert all(p["organisation_id"] == actor.organisation_id for p in again)
    assert len(_payloads(db, other_org.organisation_id)) == other_before


def test_republish_endpoint_counts_the_links(client):
    org = f"org-link-api-{new_id()[:8]}"
    registrar = make_auth_headers(user_id="registrar-1", organisation_id=org, roles=[REGISTRAR])
    created = client.post(
        f"{BASE_PATH}/people",
        json={"first_name": "Api", "last_name": "Linked", "identity_user_id": new_id()},
        headers=registrar,
    )
    assert created.status_code == 201, created.text

    res = client.post(f"{BASE_PATH}/account-links/republish", headers=registrar)
    assert res.status_code == 200, res.text
    assert res.json() == {"published": 1}

    admissions = make_auth_headers(user_id="adm-1", organisation_id=org, roles=[ADMISSIONS])
    assert client.post(f"{BASE_PATH}/account-links/republish", headers=admissions).json() == {"published": 1}


def test_republish_endpoint_needs_person_write(client):
    reader = make_auth_headers(user_id="reader-1", organisation_id=f"org-link-ro-{new_id()[:8]}", roles=[READ_ONLY])
    assert client.post(f"{BASE_PATH}/account-links/republish", headers=reader).status_code == 403
