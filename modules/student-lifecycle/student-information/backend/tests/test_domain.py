"""Unit tests for domain rules, enums, card number generation, and infrastructure model serialization."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime

import pytest
from eos_student_information.domain.enums import (
    DOCUMENT_TYPES,
    ID_CARD_STATUSES,
    PERSON_STATUSES,
    PersonStatus,
)
from eos_student_information.domain.rules import RuleViolationError, generate_card_number, validate_status_change
from eos_student_information.infrastructure.models import (
    MODELS,
    PREFIX,
    TABLES,
    IdentityCard,
    Person,
    PersonDocument,
    StatusHistoryEntry,
)


def test_domain_enums():
    assert "pending" in PERSON_STATUSES
    assert "active" in PERSON_STATUSES
    assert "suspended" in PERSON_STATUSES
    assert "graduated" in PERSON_STATUSES
    assert "withdrawn" in PERSON_STATUSES
    assert "alumnus" in PERSON_STATUSES

    assert "identity_proof" in DOCUMENT_TYPES
    assert "address_proof" in DOCUMENT_TYPES
    assert "photograph" in DOCUMENT_TYPES
    assert "prior_transcript" in DOCUMENT_TYPES
    assert "other" in DOCUMENT_TYPES

    assert "issued" in ID_CARD_STATUSES
    assert "revoked" in ID_CARD_STATUSES
    assert "expired" in ID_CARD_STATUSES


def test_status_change_validation():
    # Valid transition with reason
    validate_status_change(PersonStatus.PENDING, PersonStatus.ACTIVE, "Document verified")

    # Status unchanged -> RuleError code "status_unchanged"
    with pytest.raises(RuleViolationError) as exc_unchanged:
        validate_status_change(PersonStatus.ACTIVE, PersonStatus.ACTIVE, "Some reason")
    assert exc_unchanged.value.code == "status_unchanged"

    # Missing reason
    with pytest.raises(RuleViolationError) as exc_reason:
        validate_status_change(PersonStatus.PENDING, PersonStatus.ACTIVE, "   ")
    assert exc_reason.value.code == "reason_required"

    # Invalid status
    with pytest.raises(RuleViolationError) as exc_invalid:
        validate_status_change(PersonStatus.PENDING, "non_existent_status", "Valid reason")
    assert exc_invalid.value.code == "invalid_status"


def test_card_number_generator():
    pattern = re.compile(r"^IDC-[A-Z0-9]{4}-\d{6}-[A-F0-9]{6}$")
    fixed_time = datetime(2026, 10, 26, 12, 0, 0, tzinfo=UTC)

    card_num = generate_card_number("org-abc-1234", when=fixed_time)
    assert pattern.match(card_num)
    assert card_num.startswith("IDC-ORGA-202610-")

    # Test uniqueness and high entropy
    generated = {generate_card_number("org-test") for _ in range(100)}
    assert len(generated) == 100


def test_person_model_serialization():
    person = Person(
        id="person-1",
        organisation_id="org-1",
        first_name="Jane",
        last_name="Doe",
        preferred_name="Janie",
        date_of_birth=date(2005, 5, 15),
        gender="Female",
        identity_number="ID-123456",
        contact={"email": "jane@example.com", "phone": "1234567890", "address": "123 Street"},
        guardians=[{"name": "John Doe", "relation": "parent", "phone": "9876543210"}],
        identity_user_id=None,
        status="pending",
        status_effective_date=date(2026, 10, 26),
        source={"module": "admissions", "entity": "application", "id": "app-99"},
        created_at=datetime(2026, 10, 26, 10, 0, 0, tzinfo=UTC),
        updated_at=datetime(2026, 10, 26, 10, 0, 0, tzinfo=UTC),
    )

    data = person.to_dict()
    assert data["id"] == "person-1"
    assert data["organisation_id"] == "org-1"
    assert data["first_name"] == "Jane"
    assert data["last_name"] == "Doe"
    assert data["contact"]["email"] == "jane@example.com"
    assert data["guardians"][0]["name"] == "John Doe"
    assert data["status"] == "pending"
    assert data["status_effective_date"] == "2026-10-26"
    assert data["source"]["module"] == "admissions"


def test_status_history_model_serialization():
    entry = StatusHistoryEntry(
        id="hist-1",
        organisation_id="org-1",
        person_id="person-1",
        status="active",
        previous_status="pending",
        reason="Enrollment completed",
        effective_date=date(2026, 10, 26),
        changed_by="user-staff-1",
        changed_at=datetime(2026, 10, 26, 10, 0, 0, tzinfo=UTC),
    )

    data = entry.to_dict()
    assert data["id"] == "hist-1"
    assert data["person_id"] == "person-1"
    assert data["status"] == "active"
    assert "previous_status" not in data  # Contract schema StatusHistoryEntry excludes previous_status
    assert data["reason"] == "Enrollment completed"
    assert data["effective_date"] == "2026-10-26"
    assert data["changed_by"] == "user-staff-1"


def test_document_and_id_card_model_serialization():
    doc = PersonDocument(
        id="doc-1",
        organisation_id="org-1",
        person_id="person-1",
        type="identity_proof",
        document_id="doc-ref-uuid",
        label="Passport Scan",
        uploaded_by="user-staff-1",
        uploaded_at=datetime(2026, 10, 26, 10, 0, 0, tzinfo=UTC),
    )
    doc_data = doc.to_dict()
    assert doc_data["type"] == "identity_proof"
    assert doc_data["document_id"] == "doc-ref-uuid"

    # Card with document_id = None upon issuance
    card = IdentityCard(
        id="card-1",
        organisation_id="org-1",
        person_id="person-1",
        card_number="IDC-ORG1-202610-A1B2C3",
        status="issued",
        expires_at=date(2027, 10, 26),
        document_id=None,
        issued_by="user-staff-1",
        issued_at=datetime(2026, 10, 26, 10, 0, 0, tzinfo=UTC),
    )
    card_data = card.to_dict()
    assert card_data["card_number"] == "IDC-ORG1-202610-A1B2C3"
    assert "document_id" not in card_data  # Nullable / omitted on initial issuance


def test_tables_metadata():
    assert len(MODELS) == 4
    assert len(TABLES) == 4
    names = {t.name for t in TABLES}
    assert names == {
        f"{PREFIX}person",
        f"{PREFIX}status_history",
        f"{PREFIX}document",
        f"{PREFIX}id_card",
    }
