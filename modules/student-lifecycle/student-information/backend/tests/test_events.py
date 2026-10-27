"""Event publishing and transactional outbox verification tests for student-information.

Tests:
- All five contracted event types and exact payload shapes
- Outbox transactional boundary (events committed with entities, rolled back on error)
- A person without an email is still announced, with email null
"""

from __future__ import annotations

from datetime import date

from eos_core.db import new_id
from eos_core.events import OutboxEvent
from eos_student_information.application.service import (
    Actor,
    change_status,
    create_person,
    issue_id_card,
    revoke_id_card,
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


def _outbox_events(db, org_id: str, name: str) -> list[dict]:
    rows = db.scalars(
        select(OutboxEvent)
        .where(OutboxEvent.organisation_id == org_id, OutboxEvent.name == name)
        .order_by(OutboxEvent.occurred_at.asc())
    ).all()
    return [r.payload for r in rows]


def test_person_created_event_payload(db):
    org_id = f"org-evt-create-{new_id()[:8]}"
    actor = Actor(user_id="user-evt-1", organisation_id=org_id, permissions=ALL_PERMISSIONS)

    data = {
        "first_name": "Marcus",
        "last_name": "Aurelius",
        "contact": {"email": "marcus@rome.edu"},
        "source": {"module": "admissions", "entity": "application", "id": "app-rome-01"},
    }

    person = create_person(db, actor, data)
    db.commit()

    events = _outbox_events(db, org_id, "student-information.person.created")
    assert len(events) == 1
    payload = events[0]

    assert payload["person_id"] == person.id
    assert payload["first_name"] == "Marcus"
    assert payload["last_name"] == "Aurelius"
    assert payload["email"] == "marcus@rome.edu"
    assert payload["status"] == "pending"
    assert payload["source"] == {"module": "admissions", "entity": "application", "id": "app-rome-01"}


def test_person_created_without_email_is_still_announced(db):
    """contracts/events.yaml: every created person is announced; a missing email is null, never ''."""
    org_id = f"org-evt-noemail-{new_id()[:8]}"
    actor = Actor(user_id="user-evt-2", organisation_id=org_id, permissions=ALL_PERMISSIONS)

    data = {
        "first_name": "Ghost",
        "last_name": "Student",
        "contact": {"phone": "+12345678"},
    }

    create_person(db, actor, data)
    db.commit()

    events = _outbox_events(db, org_id, "student-information.person.created")
    assert len(events) == 1
    assert events[0]["email"] is None


def test_person_updated_event_payload(db):
    org_id = f"org-evt-update-{new_id()[:8]}"
    actor = Actor(user_id="user-evt-update", organisation_id=org_id, permissions=ALL_PERMISSIONS)

    person = create_person(
        db, actor, {"first_name": "Before", "last_name": "Update", "contact": {"email": "old@edu.com"}}
    )
    db.commit()

    update_person(db, actor, person.id, {"first_name": "After", "contact": {"email": "new@edu.com"}})
    db.commit()

    events = _outbox_events(db, org_id, "student-information.person.updated")
    assert len(events) == 1
    payload = events[0]

    assert payload["person_id"] == person.id
    assert payload["first_name"] == "After"
    assert payload["last_name"] == "Update"
    assert payload["email"] == "new@edu.com"


def test_person_updated_without_email_is_still_announced(db):
    org_id = f"org-evt-up-noemail-{new_id()[:8]}"
    actor = Actor(user_id="user-evt-up-noemail", organisation_id=org_id, permissions=ALL_PERMISSIONS)

    person = create_person(db, actor, {"first_name": "NoEmail", "last_name": "Person"})
    db.commit()

    update_person(db, actor, person.id, {"preferred_name": "Nick"})
    db.commit()

    events = _outbox_events(db, org_id, "student-information.person.updated")
    assert len(events) == 1
    assert events[0]["email"] is None and events[0]["person_id"] == person.id


def test_person_status_changed_event_payload(db):
    org_id = f"org-evt-status-{new_id()[:8]}"
    actor = Actor(user_id="user-evt-3", organisation_id=org_id, permissions=ALL_PERMISSIONS)

    person = create_person(db, actor, {"first_name": "Status", "last_name": "Student"})
    db.commit()

    change_status(db, actor, person.id, status="active", reason="Documents approved")
    db.commit()

    events = _outbox_events(db, org_id, "student-information.person.status-changed")
    assert len(events) == 1
    payload = events[0]

    assert payload["person_id"] == person.id
    assert payload["status"] == "active"
    assert payload["previous_status"] == "pending"
    assert payload["reason"] == "Documents approved"
    assert "effective_date" in payload


def test_id_card_issued_and_revoked_event_payloads(db):
    org_id = f"org-evt-card-{new_id()[:8]}"
    actor = Actor(user_id="user-evt-4", organisation_id=org_id, permissions=ALL_PERMISSIONS)

    person = create_person(db, actor, {"first_name": "Card", "last_name": "Holder"})
    db.commit()

    # Issue card
    card = issue_id_card(db, actor, person.id, {"expires_at": date(2030, 1, 1)})
    db.commit()

    issued_events = _outbox_events(db, org_id, "student-information.id-card.issued")
    assert len(issued_events) == 1
    issued_payload = issued_events[0]
    assert issued_payload["person_id"] == person.id
    assert issued_payload["card_id"] == card.id
    assert issued_payload["card_number"] == card.card_number

    # Revoke card
    revoke_id_card(db, actor, card.id, reason="Lost on transit")
    db.commit()

    revoked_events = _outbox_events(db, org_id, "student-information.id-card.revoked")
    assert len(revoked_events) == 1
    revoked_payload = revoked_events[0]
    assert revoked_payload["person_id"] == person.id
    assert revoked_payload["card_id"] == card.id
    assert revoked_payload["reason"] == "Lost on transit"


def test_transaction_rollback_preserves_outbox_atomicity(db):
    """If an operation is rolled back, the outbox event is NOT committed."""
    org_id = f"org-evt-rollback-{new_id()[:8]}"
    actor = Actor(user_id="user-evt-5", organisation_id=org_id, permissions=ALL_PERMISSIONS)

    create_person(db, actor, {"first_name": "Will", "last_name": "Rollback", "contact": {"email": "abort@test.edu"}})
    db.rollback()

    events = _outbox_events(db, org_id, "student-information.person.created")
    assert len(events) == 0
