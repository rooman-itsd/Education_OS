"""Application service layer for student-information.

Implements all core use cases:
- Person lifecycle (create, get, list/search, update profile)
- Status transitions with immutable history and validation
- Attached document reference metadata
- Logical ID card issuance and revocation with collision-resistant card numbers
- Contract-compliant transactional outbox event publishing
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Any

import sqlalchemy as sa
from eos_core import events
from eos_core.db import new_id, utcnow
from sqlalchemy.orm import Session

from ..domain.enums import DOCUMENT_TYPES, IdCardStatus, PersonStatus
from ..domain.rules import RuleViolationError, generate_card_number, validate_status_change
from ..infrastructure.models import IdentityCard, Person, PersonDocument, StatusHistoryEntry, iso


@dataclass
class Actor:
    """Represents the authenticated caller with organisation context and permissions."""

    user_id: str
    organisation_id: str
    roles: list[str] = field(default_factory=list)
    permissions: set[str] = field(default_factory=set)

    def can(self, permission: str) -> bool:
        return permission in self.permissions


class ServiceError(Exception):
    """Base application service error with HTTP status and contract-aligned error code."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message

    def to_dict(self) -> dict[str, str]:
        return {"code": self.code, "message": self.message}


def _clean_identity_number(value: Any) -> str | None:
    """Trim whitespace; an empty value is "not provided" (None), never '' (which the partial unique
    index would treat as a real number and reject on the second person)."""
    if value is None:
        return None
    cleaned = str(value).strip()
    return cleaned or None


def _assert_user_unlinked(db: Session, org_id: str, identity_user_id: str | None, except_person: str | None) -> None:
    """A sign-in account maps to at most one person in an organisation (uq_student_info_person_user)."""
    if not identity_user_id:
        return
    q = db.query(Person.id).filter(Person.organisation_id == org_id, Person.identity_user_id == identity_user_id)
    if except_person:
        q = q.filter(Person.id != except_person)
    if q.first():
        raise _conflict("duplicate_identity_user", "This identity user is already linked to another person")


def _like(term: str) -> str:
    """A contains-pattern for ilike with the user's % _ \\ taken literally."""
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _not_found(message: str) -> ServiceError:
    return ServiceError(404, "not_found", message)


def _conflict(code: str, message: str) -> ServiceError:
    return ServiceError(409, code, message)


def _rule_error(code: str, message: str) -> ServiceError:
    return ServiceError(422, code, message)


def _publish(db: Session, actor: Actor | None, name: str, organisation_id: str, payload: dict[str, Any]) -> None:
    events.publish(
        db,
        name,
        organisation_id,
        {"organisation_id": organisation_id, **payload},
        actor=actor.user_id if actor else None,
    )


def create_person(db: Session, actor: Actor, data: dict[str, Any]) -> Person:
    """Creates a new person record in 'pending' status, writes initial status history,

    and publishes the created event if contact email is provided.
    """
    org_id = actor.organisation_id

    # Check duplicate identity_number within the organisation
    identity_num = _clean_identity_number(data.get("identity_number"))
    if identity_num:
        existing = (
            db.query(Person.id).filter(Person.organisation_id == org_id, Person.identity_number == identity_num).first()
        )
        if existing:
            raise _conflict(
                "duplicate_identity_number",
                f"An identity document number '{identity_num}' already in use in this organisation",
            )
    _assert_user_unlinked(db, org_id, data.get("identity_user_id"), None)

    person = Person(
        id=new_id(),
        organisation_id=org_id,
        first_name=data["first_name"],
        last_name=data["last_name"],
        preferred_name=data.get("preferred_name"),
        date_of_birth=data.get("date_of_birth"),
        gender=data.get("gender"),
        identity_number=identity_num,
        contact=data.get("contact"),
        guardians=data.get("guardians") or [],
        identity_user_id=data.get("identity_user_id"),
        status=PersonStatus.PENDING.value,
        status_effective_date=date.today(),
        source=data.get("source"),
    )
    db.add(person)

    # Initial status history record
    initial_history = StatusHistoryEntry(
        id=new_id(),
        organisation_id=org_id,
        person_id=person.id,
        status=PersonStatus.PENDING.value,
        previous_status=None,
        reason="Initial person record creation",
        effective_date=person.status_effective_date,
        changed_by=actor.user_id,
        changed_at=utcnow(),
    )
    db.add(initial_history)

    # Every created person is announced (contracts/events.yaml); email is null when not provided.
    contact = data.get("contact") or {}
    email = contact.get("email") if isinstance(contact, dict) else None
    _publish(
        db,
        actor,
        "student-information.person.created",
        org_id,
        {
            "person_id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "email": email or None,
            "status": person.status,
            "source": person.source,
        },
    )

    db.flush()
    return person


def get_person(db: Session, actor: Actor, person_id: str) -> Person:
    """Retrieves a single person record by id within the caller's organisation."""
    person = db.query(Person).filter(Person.id == person_id, Person.organisation_id == actor.organisation_id).first()
    if not person:
        raise _not_found("Person not found in your organisation")
    return person


def list_people(
    db: Session,
    actor: Actor,
    *,
    q: str | None = None,
    identity_number: str | None = None,
    identity_user_id: str | None = None,
    status: list[str] | str | None = None,
    page: int = 1,
    page_size: int = 50,
) -> dict[str, Any]:
    """Finds people within caller's organisation supporting exact identity search,

    status filtering, partial text search on name/email, and pagination.
    """
    query = db.query(Person).filter(Person.organisation_id == actor.organisation_id)

    if identity_number:
        query = query.filter(Person.identity_number == identity_number)
    if identity_user_id:
        query = query.filter(Person.identity_user_id == identity_user_id)

    if status:
        if isinstance(status, str):
            statuses = [s.strip() for s in status.split(",") if s.strip()]
        else:
            statuses = list(status)
        if statuses:
            query = query.filter(Person.status.in_(statuses))

    if q and q.strip():
        term = _like(q.strip())
        # Case-insensitive contains on first name, last name and the contact email (the contract's q), not on
        # the rest of the contact record
        query = query.filter(
            sa.or_(
                Person.first_name.ilike(term, escape="\\"),
                Person.last_name.ilike(term, escape="\\"),
                Person.contact["email"].as_string().ilike(term, escape="\\"),
            )
        )

    total = query.count()
    limit = max(1, min(page_size, 200))
    offset = max(0, (page - 1) * limit)
    items = query.order_by(Person.created_at.desc()).offset(offset).limit(limit).all()

    return {
        "items": [p.to_dict() for p in items],
        "total": total,
        "page": page,
        "page_size": limit,
    }


def update_person(db: Session, actor: Actor, person_id: str, updates: dict[str, Any]) -> Person:
    """Updates profile fields. Does NOT allow direct status changes."""
    person = get_person(db, actor, person_id)

    # Disallow direct status mutation through update_person
    if "status" in updates:
        raise _rule_error("status_immutable", "Cannot update status directly; use /people/{id}/status")

    # If identity_number changed, verify duplicate constraint
    if "identity_number" in updates:
        updates = {**updates, "identity_number": _clean_identity_number(updates["identity_number"])}
    new_identity = updates.get("identity_number")
    if new_identity is not None and new_identity != person.identity_number:
        existing = (
            db.query(Person.id)
            .filter(
                Person.organisation_id == actor.organisation_id,
                Person.identity_number == new_identity,
                Person.id != person_id,
            )
            .first()
        )
        if existing:
            raise _conflict(
                "duplicate_identity_number",
                f"An identity document number '{new_identity}' already in use in this organisation",
            )
    if updates.get("identity_user_id") and updates["identity_user_id"] != person.identity_user_id:
        _assert_user_unlinked(db, actor.organisation_id, updates["identity_user_id"], person_id)

    # Apply permitted fields
    for field_name in (
        "first_name",
        "last_name",
        "preferred_name",
        "date_of_birth",
        "gender",
        "identity_number",
        "contact",
        "guardians",
        "identity_user_id",
    ):
        if field_name in updates:
            setattr(person, field_name, updates[field_name])

    person.updated_at = utcnow()

    contact = person.contact or {}
    email = contact.get("email") if isinstance(contact, dict) else None
    _publish(
        db,
        actor,
        "student-information.person.updated",
        actor.organisation_id,
        {
            "person_id": person.id,
            "first_name": person.first_name,
            "last_name": person.last_name,
            "email": email or None,
        },
    )

    db.flush()
    return person


def change_status(
    db: Session,
    actor: Actor,
    person_id: str,
    *,
    status: str,
    reason: str,
    effective_date: date | None = None,
) -> Person:
    """Changes a person's status with an audit reason, appends to immutable history,

    and publishes student-information.person.status-changed.
    """
    person = get_person(db, actor, person_id)

    try:
        validate_status_change(person.status, status, reason)
    except RuleViolationError as exc:
        raise _rule_error(exc.code, exc.message) from exc

    prev_status = person.status
    eff_date = effective_date or date.today()

    person.status = status
    person.status_effective_date = eff_date
    person.updated_at = utcnow()

    # Append to immutable status history
    history = StatusHistoryEntry(
        id=new_id(),
        organisation_id=actor.organisation_id,
        person_id=person.id,
        status=status,
        previous_status=prev_status,
        reason=reason,
        effective_date=eff_date,
        changed_by=actor.user_id,
        changed_at=utcnow(),
    )
    db.add(history)

    _publish(
        db,
        actor,
        "student-information.person.status-changed",
        actor.organisation_id,
        {
            "person_id": person.id,
            "status": status,
            "previous_status": prev_status,
            "reason": reason,
            "effective_date": iso(eff_date),
        },
    )

    db.flush()
    return person


def get_status_history(db: Session, actor: Actor, person_id: str) -> list[dict[str, Any]]:
    """Retrieves full status history for a person, most recent first."""
    get_person(db, actor, person_id)  # Ensure person exists in organisation
    entries = (
        db.query(StatusHistoryEntry)
        .filter(
            StatusHistoryEntry.organisation_id == actor.organisation_id,
            StatusHistoryEntry.person_id == person_id,
        )
        .order_by(StatusHistoryEntry.changed_at.desc())
        .all()
    )
    return [e.to_dict() for e in entries]


def attach_document(db: Session, actor: Actor, person_id: str, data: dict[str, Any]) -> PersonDocument:
    """Attaches a document reference stored in platform/documents."""
    get_person(db, actor, person_id)

    doc_type = data["type"]
    if doc_type not in DOCUMENT_TYPES:
        raise _rule_error("invalid_document_type", f"Unknown document type '{doc_type}'")

    doc = PersonDocument(
        id=new_id(),
        organisation_id=actor.organisation_id,
        person_id=person_id,
        type=doc_type,
        document_id=data["document_id"],
        label=data.get("label"),
        uploaded_by=actor.user_id,
        uploaded_at=utcnow(),
    )
    db.add(doc)
    db.flush()
    return doc


def list_documents(db: Session, actor: Actor, person_id: str) -> list[dict[str, Any]]:
    """Lists document references attached to a person."""
    get_person(db, actor, person_id)
    docs = (
        db.query(PersonDocument)
        .filter(
            PersonDocument.organisation_id == actor.organisation_id,
            PersonDocument.person_id == person_id,
        )
        .order_by(PersonDocument.uploaded_at.desc())
        .all()
    )
    return [d.to_dict() for d in docs]


def delete_document(db: Session, actor: Actor, person_id: str, document_id: str) -> None:
    """Removes a document reference from a person's record."""
    get_person(db, actor, person_id)

    # The path id is the PersonDocument reference id (contract), not the platform document id
    doc = (
        db.query(PersonDocument)
        .filter(
            PersonDocument.organisation_id == actor.organisation_id,
            PersonDocument.person_id == person_id,
            PersonDocument.id == document_id,
        )
        .first()
    )
    if not doc:
        raise _not_found("Document reference not found on this person's record")

    db.delete(doc)
    db.flush()


def issue_id_card(
    db: Session,
    actor: Actor,
    person_id: str,
    data: dict[str, Any] | None = None,
) -> IdentityCard:
    """Issues a new logical ID card. Enforces one active card per person with retry on card number collisions."""
    get_person(db, actor, person_id)

    # Verify no card is currently active (issued)
    active_card = (
        db.query(IdentityCard.id)
        .filter(
            IdentityCard.organisation_id == actor.organisation_id,
            IdentityCard.person_id == person_id,
            IdentityCard.status == IdCardStatus.ISSUED.value,
        )
        .first()
    )
    if active_card:
        raise _conflict("active_card_exists", "Person already has an active card; revoke it before issuing a new one")

    # Generate unique card number with collision retry (up to 3 attempts)
    card_number: str | None = None
    for _ in range(3):
        candidate = generate_card_number(actor.organisation_id)
        collision = db.query(IdentityCard.id).filter(IdentityCard.card_number == candidate).first()
        if not collision:
            card_number = candidate
            break

    if not card_number:
        raise ServiceError(500, "card_generation_failed", "Failed to generate a unique card number after retries")

    input_data = data or {}
    card = IdentityCard(
        id=new_id(),
        organisation_id=actor.organisation_id,
        person_id=person_id,
        card_number=card_number,
        status=IdCardStatus.ISSUED.value,
        expires_at=input_data.get("expires_at"),
        document_id=None,  # Nullable upon initial logical issuance
        issued_by=actor.user_id,
        issued_at=utcnow(),
    )
    db.add(card)

    _publish(
        db,
        actor,
        "student-information.id-card.issued",
        actor.organisation_id,
        {
            "person_id": person_id,
            "card_id": card.id,
            "card_number": card.card_number,
        },
    )

    db.flush()
    return card


def list_id_cards(db: Session, actor: Actor, person_id: str) -> list[dict[str, Any]]:
    """Lists ID cards issued to a person, most recent first."""
    get_person(db, actor, person_id)
    cards = (
        db.query(IdentityCard)
        .filter(
            IdentityCard.organisation_id == actor.organisation_id,
            IdentityCard.person_id == person_id,
        )
        .order_by(IdentityCard.issued_at.desc())
        .all()
    )
    return [c.to_dict() for c in cards]


def revoke_id_card(db: Session, actor: Actor, card_id: str, reason: str) -> IdentityCard:
    """Revokes an active ID card with a required reason and publishes student-information.id-card.revoked."""
    if not reason or not reason.strip():
        raise _rule_error("reason_required", "A reason is required to revoke an ID card")

    card = (
        db.query(IdentityCard)
        .filter(
            IdentityCard.id == card_id,
            IdentityCard.organisation_id == actor.organisation_id,
        )
        .first()
    )
    if not card:
        raise _not_found("ID card not found in your organisation")

    if card.status != IdCardStatus.ISSUED.value:
        raise _conflict(
            "card_not_active",
            f"Card is not active (current status: {card.status})",
        )

    card.status = IdCardStatus.REVOKED.value
    card.revoked_by = actor.user_id
    card.revoked_at = utcnow()
    card.revoked_reason = reason.strip()

    _publish(
        db,
        actor,
        "student-information.id-card.revoked",
        actor.organisation_id,
        {
            "person_id": card.person_id,
            "card_id": card.id,
            "reason": card.revoked_reason,
        },
    )

    db.flush()
    return card
