"""Contract drift tests for student-information.

Compares implementation against the actual contract files:
- contracts/openapi.yaml
- contracts/permissions.yaml
- contracts/events.yaml

Ensures that code follows contracts and fails immediately if contracts drift.
Preserves the flagged required-email contract discrepancy as an explicit check.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from eos_student_information.api.deps import (
    PERM_DOCUMENT_MANAGE,
    PERM_ID_CARD_MANAGE,
    PERM_PERSON_READ,
    PERM_PERSON_WRITE,
    PERM_STATUS_MANAGE,
)
from eos_student_information.api.router import VALID_STATUSES, router
from eos_student_information.domain.enums import DocumentType, IdCardStatus, PersonStatus

CONTRACTS_DIR = Path(__file__).resolve().parents[2] / "contracts"
METHODS = {"get", "post", "patch", "put", "delete"}


@pytest.fixture(scope="module")
def openapi():
    return yaml.safe_load((CONTRACTS_DIR / "openapi.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def permissions():
    return yaml.safe_load((CONTRACTS_DIR / "permissions.yaml").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def events():
    return yaml.safe_load((CONTRACTS_DIR / "events.yaml").read_text(encoding="utf-8"))


def test_routes_and_methods_match_openapi(openapi):
    """Every path and HTTP method in contracts/openapi.yaml exists on the FastAPI router."""
    contract_routes = {
        (method.upper(), path)
        for path, path_item in openapi["paths"].items()
        for method in path_item
        if method in METHODS
    }

    implemented_routes = {
        (method, route.path) for route in router.routes for method in route.methods if method.lower() in METHODS
    }

    assert implemented_routes == contract_routes
    assert len(contract_routes) == 12


def test_enums_match_openapi_schemas(openapi):
    """Domain enums strictly match OpenAPI schema component enums."""
    schemas = openapi["components"]["schemas"]

    assert set(PersonStatus) == set(schemas["PersonStatus"]["enum"])
    assert VALID_STATUSES == set(schemas["PersonStatus"]["enum"])
    assert set(DocumentType) == set(schemas["PersonDocumentType"]["enum"])
    assert set(IdCardStatus) == set(schemas["IdentityCardStatus"]["enum"])


def test_contact_details_schema_preservation(openapi):
    """Preserves 'contact' schema with email, phone, address (not contact_details)."""
    schemas = openapi["components"]["schemas"]
    contact_schema = schemas["ContactDetails"]
    properties = contact_schema["properties"]

    assert set(properties.keys()) == {"email", "phone", "address"}
    person_input_props = schemas["PersonInput"]["properties"]
    assert "contact" in person_input_props
    assert "$ref" in person_input_props["contact"]
    assert person_input_props["contact"]["$ref"] == "#/components/schemas/ContactDetails"


def test_status_history_entry_omits_previous_status(openapi):
    """Public StatusHistoryEntry schema does NOT expose previous_status."""
    schemas = openapi["components"]["schemas"]
    hist_props = schemas["StatusHistoryEntry"]["properties"]

    assert "previous_status" not in hist_props
    assert "status" in hist_props
    assert "reason" in hist_props
    assert "effective_date" in hist_props
    assert "changed_by" in hist_props
    assert "changed_at" in hist_props


def test_identity_card_input_schema_has_only_expires_at(openapi):
    """IdentityCardInput request schema contains only optional expires_at."""
    schemas = openapi["components"]["schemas"]
    card_input = schemas["IdentityCardInput"]

    assert set(card_input.get("properties", {}).keys()) == {"expires_at"}


def test_error_schemas_contract_shapes(openapi):
    """ConflictError and RuleError schemas match the contract enum codes."""
    schemas = openapi["components"]["schemas"]

    conflict_codes = schemas["ConflictError"]["properties"]["code"]["enum"]
    assert set(conflict_codes) == {
        "duplicate_identity_number",
        "duplicate_identity_user",
        "active_card_exists",
        "card_not_active",
        "conflict",
    }

    rule_codes = schemas["RuleError"]["properties"]["code"]["enum"]
    assert set(rule_codes) == {"status_unchanged"}


def test_permission_catalogue_matches_dependency_constants(permissions):
    """Declared permission constants in deps.py match contracts/permissions.yaml."""
    contract_keys = {p["key"] for p in permissions["permissions"]}
    declared_keys = {
        PERM_PERSON_READ,
        PERM_PERSON_WRITE,
        PERM_STATUS_MANAGE,
        PERM_DOCUMENT_MANAGE,
        PERM_ID_CARD_MANAGE,
    }

    assert declared_keys == contract_keys
    assert len(declared_keys) == 5


def test_contracted_events_catalog(events):
    """All 5 events in contracts/events.yaml are accounted for."""
    contract_event_names = {e["name"] for e in events["events"]}
    expected_event_names = {
        "student-information.person.created",
        "student-information.person.updated",
        "student-information.person.status-changed",
        "student-information.id-card.issued",
        "student-information.id-card.revoked",
    }
    assert contract_event_names == expected_event_names


def test_unresolved_email_contract_discrepancy_flagged(openapi, events):
    """Validates that the contract discrepancy remains visible and unmasked.

    In contracts/events.yaml:
      student-information.person.created payload specifies 'email: string' (mandatory).
    In contracts/openapi.yaml:
      PersonInput.contact.email is optional (not in required).

    The code deliberately does NOT emit an empty string fallback or modify contracts.
    """
    created_event = next(e for e in events["events"] if e["name"] == "student-information.person.created")
    assert "email" in created_event["payload"]
    assert created_event["payload"]["email"] == "string"

    person_input = openapi["components"]["schemas"]["PersonInput"]
    contact_schema = openapi["components"]["schemas"]["ContactDetails"]
    assert "email" not in person_input.get("required", [])
    assert "email" not in contact_schema.get("required", [])
