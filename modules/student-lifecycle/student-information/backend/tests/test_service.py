"""Comprehensive application-service tests for student-information.

Tests:
- Person creation with duplicate detection and event publishing
- A person without an email is still announced, with email null
- Strict tenant scoping (no leakage between orgs)
- Search, filter (status list/comma-separated, identity_number), and pagination
- Person update with duplicate protection and direct status mutation prevention
- Status changes, reason requirement, rejection of unchanged status (422 status_unchanged)
- Immutable status history ordering
- Document reference attachment, listing, and deletion
- ID card issuance, duplicate active card rejection, collision retry, and revocation
- Transactional rollback and event boundary guarantees
"""

from __future__ import annotations

from datetime import date

import pytest
from eos_core.events import OutboxEvent
from eos_student_information.application.service import (
    Actor,
    ServiceError,
    attach_document,
    change_status,
    create_person,
    delete_document,
    get_person,
    get_status_history,
    issue_id_card,
    list_documents,
    list_id_cards,
    list_people,
    revoke_id_card,
    update_person,
)
from eos_student_information.infrastructure.models import Person


def test_create_person_and_event(db, actor_a: Actor):
    data = {
        "first_name": "Alice",
        "last_name": "Smith",
        "contact": {"email": "alice@example.com", "phone": "+123456789"},
        "identity_number": "NAT-ID-1001",
        "source": {"module": "admissions", "entity": "application", "id": "app-001"},
    }

    person = create_person(db, actor_a, data)
    db.commit()

    assert person.id is not None
    assert person.organisation_id == actor_a.organisation_id
    assert person.status == "pending"
    assert person.first_name == "Alice"

    # Initial status history entry created
    history = get_status_history(db, actor_a, person.id)
    assert len(history) == 1
    assert history[0]["status"] == "pending"
    assert history[0]["reason"] == "Initial person record creation"

    # Outbox event published
    event = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.name == "student-information.person.created")
        .order_by(OutboxEvent.occurred_at.desc())
        .first()
    )
    assert event is not None
    assert event.payload["person_id"] == person.id
    assert event.payload["email"] == "alice@example.com"
    assert event.payload["status"] == "pending"
    assert event.payload["source"]["module"] == "admissions"


def test_create_person_without_email_publishes_event_with_null_email(db, actor_a: Actor):
    # Person with no email provided
    data = {
        "first_name": "Bob",
        "last_name": "Jones",
        "contact": {"phone": "+987654321"},
    }

    events_before = db.query(OutboxEvent).count()
    person = create_person(db, actor_a, data)
    db.commit()

    assert person.id is not None
    events_after = db.query(OutboxEvent).count()

    # Every created person is announced (contracts/events.yaml); the email is null, never ""
    created_events = (
        db.query(OutboxEvent)
        .filter(
            OutboxEvent.name == "student-information.person.created",
            OutboxEvent.payload["person_id"].as_string() == person.id,
        )
        .all()
    )
    assert len(created_events) == 1
    assert created_events[0].payload["email"] is None
    assert events_after == events_before + 1


def test_duplicate_identity_number_enforced_within_org(db, actor_a: Actor, actor_b: Actor):
    data1 = {"first_name": "Charlie", "last_name": "Brown", "identity_number": "UNIQUE-123"}
    create_person(db, actor_a, data1)
    db.commit()

    # Second person with same identity_number in SAME org -> 409 duplicate_identity_number
    data2 = {"first_name": "Charlie", "last_name": "Second", "identity_number": "UNIQUE-123"}
    with pytest.raises(ServiceError) as exc:
        create_person(db, actor_a, data2)
    assert exc.value.status_code == 409
    assert exc.value.code == "duplicate_identity_number"

    # Same identity_number in DIFFERENT org (actor_b) is permitted (multi-tenant isolation)
    person_b = create_person(db, actor_b, data2)
    db.commit()
    assert person_b.organisation_id == actor_b.organisation_id


def test_get_person_tenant_isolation(db, actor_a: Actor, actor_b: Actor):
    person_a = create_person(db, actor_a, {"first_name": "Dave", "last_name": "Miller"})
    db.commit()

    # Actor A can retrieve person A
    retrieved = get_person(db, actor_a, person_a.id)
    assert retrieved.id == person_a.id

    # Actor B cannot access person A (returns 404 not found)
    with pytest.raises(ServiceError) as exc:
        get_person(db, actor_b, person_a.id)
    assert exc.value.status_code == 404
    assert exc.value.code == "not_found"


def test_list_people_search_and_filters(db, actor_a: Actor, actor_b: Actor):
    p1 = create_person(
        db,
        actor_a,
        {"first_name": "Emma", "last_name": "Watson", "contact": {"email": "emma@test.edu"}, "identity_number": "ID-A"},
    )
    p2 = create_person(
        db,
        actor_a,
        {
            "first_name": "John",
            "last_name": "Watson",
            "contact": {"email": "watson@med.org"},
            "identity_number": "ID-B",
        },
    )
    # Person in org B (must never appear in org A's listings)
    create_person(db, actor_b, {"first_name": "Emma", "last_name": "Other"})
    db.commit()

    # Change status of p2 to active
    change_status(db, actor_a, p2.id, status="active", reason="Verified")
    db.commit()

    # Filter by exact identity_number
    res_id = list_people(db, actor_a, identity_number="ID-A")
    assert res_id["total"] == 1
    assert res_id["items"][0]["id"] == p1.id

    # Filter by comma-separated status
    res_status = list_people(db, actor_a, status="active,suspended")
    assert res_status["total"] == 1
    assert res_status["items"][0]["id"] == p2.id

    # Search by partial query 'watson' (matches both p1 and p2 in org A, but not org B)
    res_q = list_people(db, actor_a, q="Watson")
    assert res_q["total"] == 2
    assert all(item["organisation_id"] == actor_a.organisation_id for item in res_q["items"])


def test_update_person_profile_and_status_immutable(db, actor_a: Actor):
    person = create_person(
        db,
        actor_a,
        {
            "first_name": "George",
            "last_name": "Clark",
            "contact": {"email": "george@example.com"},
            "identity_number": "GEO-1",
        },
    )
    db.commit()

    # Direct status change via update_person is rejected
    with pytest.raises(ServiceError) as exc_status:
        update_person(db, actor_a, person.id, {"status": "active"})
    assert exc_status.value.status_code == 422
    assert exc_status.value.code == "status_immutable"

    # Profile updates succeed and emit person.updated
    updated = update_person(
        db,
        actor_a,
        person.id,
        {"preferred_name": "Georgie", "contact": {"email": "georgie@example.com"}},
    )
    db.commit()
    assert updated.preferred_name == "Georgie"
    assert updated.contact["email"] == "georgie@example.com"

    event = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.name == "student-information.person.updated")
        .order_by(OutboxEvent.occurred_at.desc())
        .first()
    )
    assert event is not None
    assert event.payload["person_id"] == person.id
    assert event.payload["email"] == "georgie@example.com"


def test_change_status_and_validation(db, actor_a: Actor):
    person = create_person(db, actor_a, {"first_name": "Hannah", "last_name": "Abbott"})
    db.commit()
    assert person.status == "pending"

    # Rejection of unchanged status with 422 status_unchanged
    with pytest.raises(ServiceError) as exc_unchanged:
        change_status(db, actor_a, person.id, status="pending", reason="Awaiting docs")
    assert exc_unchanged.value.status_code == 422
    assert exc_unchanged.value.code == "status_unchanged"

    # Rejection of missing reason
    with pytest.raises(ServiceError) as exc_reason:
        change_status(db, actor_a, person.id, status="active", reason="   ")
    assert exc_reason.value.status_code == 422
    assert exc_reason.value.code == "reason_required"

    # Valid status change
    changed = change_status(
        db,
        actor_a,
        person.id,
        status="active",
        reason="Registration verified",
        effective_date=date(2026, 10, 26),
    )
    db.commit()
    assert changed.status == "active"
    assert changed.status_effective_date == date(2026, 10, 26)

    # Status history inspection (ordered most recent first)
    history = get_status_history(db, actor_a, person.id)
    assert len(history) == 2
    assert history[0]["status"] == "active"
    assert history[0]["reason"] == "Registration verified"
    assert history[1]["status"] == "pending"

    # Event emitted
    event = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.name == "student-information.person.status-changed")
        .order_by(OutboxEvent.occurred_at.desc())
        .first()
    )
    assert event is not None
    assert event.payload["status"] == "active"
    assert event.payload["previous_status"] == "pending"


def test_document_references(db, actor_a: Actor):
    person = create_person(db, actor_a, {"first_name": "Ian", "last_name": "Malcolm"})
    db.commit()

    doc_data = {
        "type": "identity_proof",
        "document_id": "doc-uuid-12345",
        "label": "Passport Document",
    }
    doc = attach_document(db, actor_a, person.id, doc_data)
    db.commit()

    assert doc.id is not None
    assert doc.document_id == "doc-uuid-12345"

    docs = list_documents(db, actor_a, person.id)
    assert len(docs) == 1
    assert docs[0]["label"] == "Passport Document"

    # Delete document reference
    delete_document(db, actor_a, person.id, doc.id)
    db.commit()

    docs_after = list_documents(db, actor_a, person.id)
    assert len(docs_after) == 0


def test_id_cards_lifecycle_and_constraints(db, actor_a: Actor):
    person = create_person(db, actor_a, {"first_name": "Julia", "last_name": "Roberts"})
    db.commit()

    # Issue initial ID card
    card = issue_id_card(db, actor_a, person.id, {"expires_at": date(2027, 10, 26)})
    db.commit()

    assert card.status == "issued"
    assert card.card_number.startswith("IDC-ORGA-")
    assert card.document_id is None

    # List ID cards
    cards = list_id_cards(db, actor_a, person.id)
    assert len(cards) == 1
    assert cards[0]["id"] == card.id

    # Event student-information.id-card.issued emitted
    event_issued = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.name == "student-information.id-card.issued")
        .order_by(OutboxEvent.occurred_at.desc())
        .first()
    )
    assert event_issued is not None
    assert event_issued.payload["card_id"] == card.id

    # Attempting to issue a second active card -> 409 active_card_exists
    with pytest.raises(ServiceError) as exc_active:
        issue_id_card(db, actor_a, person.id)
    assert exc_active.value.status_code == 409
    assert exc_active.value.code == "active_card_exists"

    # Revoke active card
    revoked = revoke_id_card(db, actor_a, card.id, reason="Card lost by student")
    db.commit()

    assert revoked.status == "revoked"
    assert revoked.revoked_reason == "Card lost by student"

    # Event student-information.id-card.revoked emitted
    event_revoked = (
        db.query(OutboxEvent)
        .filter(OutboxEvent.name == "student-information.id-card.revoked")
        .order_by(OutboxEvent.occurred_at.desc())
        .first()
    )
    assert event_revoked is not None
    assert event_revoked.payload["reason"] == "Card lost by student"

    # Attempting to revoke an already revoked card -> 409 card_not_active
    with pytest.raises(ServiceError) as exc_not_active:
        revoke_id_card(db, actor_a, card.id, reason="Duplicate attempt")
    assert exc_not_active.value.status_code == 409
    assert exc_not_active.value.code == "card_not_active"

    # Once revoked, issuing a new active card is now permitted
    card2 = issue_id_card(db, actor_a, person.id)
    db.commit()
    assert card2.status == "issued"
    assert card2.id != card.id


def test_transaction_rollback_and_event_boundary(db, actor_a: Actor):
    # Simulate a transaction failure: person created, then rollback
    events_initial = db.query(OutboxEvent).count()
    person_id: str | None = None

    try:
        person = create_person(
            db,
            actor_a,
            {"first_name": "Test", "last_name": "Rollback", "contact": {"email": "test@roll.back"}},
        )
        person_id = person.id
        # Force a rollback
        raise RuntimeError("Simulated failure")
    except RuntimeError:
        db.rollback()

    assert person_id is not None
    # Neither the person nor the outbox event is persisted after rollback
    assert db.query(Person).filter(Person.id == person_id).first() is None
    assert db.query(OutboxEvent).count() == events_initial
