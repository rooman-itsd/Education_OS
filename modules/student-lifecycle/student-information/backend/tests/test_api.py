"""Comprehensive API tests for student-information (FastAPI router, auth dependencies & schemas).

Tests:
1. Authentication: missing bearer, malformed header, invalid signature, missing org claim.
2. Authorization: route-level permission enforcement according to contracts/permissions.yaml.
3. Request Validation: 422 responses for malformed payloads, extra fields, unknown statuses.
4. Response Schemas: strict validation of response dicts against Pydantic models mirroring openapi.yaml.
5. Person CRUD & Search: full lifecycle, contact preservation, search, comma-separated status filtering.
6. Status Management: status changes, 422 status_unchanged RuleError, StatusHistoryEntry without previous_status.
7. Documents: attach, list, delete (204), 404 for missing.
8. ID Cards: issuance (IdentityCardInput with expires_at only), 409 active_card_exists, revoke, 409 card_not_active.
9. Tenant Isolation: complete cross-tenant invisibility (404s, list scoping, duplicate identity_number allowed across orgs).
10. Transactional Outbox: verify event generation boundary; a person without an email is still announced.
"""

from __future__ import annotations

from datetime import timedelta

import jwt
from conftest import ADMISSIONS, NO_ACCESS, READ_ONLY, REGISTRAR
from eos_core.db import SessionLocal, utcnow
from eos_core.events import OutboxEvent
from eos_core.settings import settings
from eos_student_information.api import schemas as s
from eos_student_information.api.deps import (
    PERM_DOCUMENT_MANAGE,
    PERM_ID_CARD_MANAGE,
    PERM_PERSON_READ,
    PERM_PERSON_WRITE,
    PERM_STATUS_MANAGE,
)
from sqlalchemy import select

BASE_PATH = "/api/v1/student-information"


def mint_token(
    *,
    user_id: str = "test-user-1",
    organisation_id: str | None = "org-alpha-1234",
    roles: list[str] | None = None,
    sa: bool = False,
    secret: str | None = None,
) -> str:
    now = utcnow()
    payload = {
        "sub": user_id,
        "org": organisation_id,
        "roles": roles or [],
        "sa": sa,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(hours=1)).timestamp()),
    }
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm="HS256")


def make_auth_headers(
    *,
    user_id: str = "test-user-1",
    organisation_id: str | None = "org-alpha-1234",
    roles: list[str] | None = None,
    sa: bool = False,
    secret: str | None = None,
) -> dict[str, str]:
    token = mint_token(
        user_id=user_id,
        organisation_id=organisation_id,
        roles=roles,
        sa=sa,
        secret=secret,
    )
    return {"Authorization": f"Bearer {token}"}


def _get_outbox_events(org_id: str, event_name: str) -> list[dict]:
    with SessionLocal() as session:
        events = session.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.organisation_id == org_id, OutboxEvent.name == event_name)
            .order_by(OutboxEvent.occurred_at.asc())
        ).all()
        return [e.payload for e in events]


# =====================================================================
# 1. Authentication & Token Verification Tests
# =====================================================================


def test_auth_missing_header(client):
    res = client.get(f"{BASE_PATH}/people")
    assert res.status_code == 401
    assert "missing bearer token" in res.json()["detail"].lower()


def test_auth_malformed_header(client):
    res = client.get(f"{BASE_PATH}/people", headers={"Authorization": "Basic dXNlcjpwYXNz"})
    assert res.status_code == 401
    assert "missing bearer token" in res.json()["detail"].lower()


def test_auth_invalid_signature(client):
    headers = make_auth_headers(secret="wrong-secret-signature-key-12345678")
    res = client.get(f"{BASE_PATH}/people", headers=headers)
    assert res.status_code == 401
    assert "invalid token" in res.json()["detail"].lower()


def test_auth_missing_organisation_claim(client):
    headers = make_auth_headers(organisation_id=None)
    res = client.get(f"{BASE_PATH}/people", headers=headers)
    assert res.status_code == 403
    assert "organisation user" in res.json()["detail"].lower()


# =====================================================================
# 2. Authorization & Permission Enforcement Tests
# =====================================================================


def test_permission_person_read_enforced(client):
    # A user whose roles carry no student-information key
    headers = make_auth_headers(roles=[NO_ACCESS])
    res = client.get(f"{BASE_PATH}/people", headers=headers)
    assert res.status_code == 403
    assert PERM_PERSON_READ in res.json()["detail"]


def test_permission_person_write_enforced(client):
    # User has read-only permission but tries to create a person
    headers = make_auth_headers(roles=[READ_ONLY])
    res = client.post(
        f"{BASE_PATH}/people",
        headers=headers,
        json={"first_name": "Read", "last_name": "Only"},
    )
    assert res.status_code == 403
    assert PERM_PERSON_WRITE in res.json()["detail"]


def test_permission_status_manage_enforced(client, headers_a):
    # First create a person as the registrar
    create_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "Status", "last_name": "Target"},
    )
    person_id = create_res.json()["id"]

    # Try changing status with read/write only (lacking status:manage)
    no_status_perm = make_auth_headers(roles=[ADMISSIONS])
    res = client.put(
        f"{BASE_PATH}/people/{person_id}/status",
        headers=no_status_perm,
        json={"status": "active", "reason": "Enrollment confirmed"},
    )
    assert res.status_code == 403
    assert PERM_STATUS_MANAGE in res.json()["detail"]


def test_permission_document_manage_enforced(client, headers_a):
    create_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "Doc", "last_name": "Target"},
    )
    person_id = create_res.json()["id"]

    no_doc_perm = make_auth_headers(roles=[READ_ONLY])
    res = client.post(
        f"{BASE_PATH}/people/{person_id}/documents",
        headers=no_doc_perm,
        json={"type": "identity_proof", "document_id": "doc-uuid-101"},
    )
    assert res.status_code == 403
    assert PERM_DOCUMENT_MANAGE in res.json()["detail"]


def test_permission_id_card_manage_enforced(client, headers_a):
    create_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "Card", "last_name": "Target"},
    )
    person_id = create_res.json()["id"]

    no_card_perm = make_auth_headers(roles=[READ_ONLY])
    res = client.post(
        f"{BASE_PATH}/people/{person_id}/id-cards",
        headers=no_card_perm,
        json={},
    )
    assert res.status_code == 403
    assert PERM_ID_CARD_MANAGE in res.json()["detail"]


# =====================================================================
# 3. Request Validation Tests (Pydantic / 422)
# =====================================================================


def test_validation_person_missing_required_fields(client, headers_a):
    res = client.post(f"{BASE_PATH}/people", headers=headers_a, json={"first_name": "OnlyFirst"})
    assert res.status_code == 422


def test_validation_person_extra_field_forbidden(client, headers_a):
    res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={
            "first_name": "Alice",
            "last_name": "Smith",
            "uncontracted_extra_field": "disallowed",
        },
    )
    assert res.status_code == 422


def test_validation_invalid_status_query(client, headers_a):
    res = client.get(f"{BASE_PATH}/people?status=unknown_status", headers=headers_a)
    assert res.status_code == 422
    assert res.json()["detail"]["code"] == "invalid_status"


def test_validation_document_invalid_type(client, headers_a):
    create_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "Doc", "last_name": "TypeTest"},
    )
    person_id = create_res.json()["id"]

    res = client.post(
        f"{BASE_PATH}/people/{person_id}/documents",
        headers=headers_a,
        json={"type": "invalid_type", "document_id": "doc-uuid-1"},
    )
    assert res.status_code == 422


def test_validation_revoke_card_empty_reason(client, headers_a):
    res = client.post(
        f"{BASE_PATH}/id-cards/any-card-id/revoke",
        headers=headers_a,
        json={"reason": ""},
    )
    assert res.status_code == 422


# =====================================================================
# 4. Person CRUD, Status History, & Contract Error Mappings
# =====================================================================


def test_person_lifecycle_and_schemas(client, headers_a):
    # 1. Create person
    payload = {
        "first_name": "Eleanor",
        "last_name": "Vane",
        "preferred_name": "Ellie",
        "date_of_birth": "2005-04-12",
        "gender": "female",
        "identity_number": "NAT-EL-5501",
        "contact": {
            "email": "eleanor.vane@example.com",
            "phone": "+1-555-0199",
            "address": "12 High St, Cambridge",
        },
        "guardians": [
            {
                "name": "Arthur Vane",
                "relation": "parent",
                "phone": "+1-555-0100",
                "email": "arthur.vane@example.com",
            }
        ],
        "source": {
            "module": "admissions",
            "entity": "application",
            "id": "app-vane-2026",
        },
    }

    create_res = client.post(f"{BASE_PATH}/people", headers=headers_a, json=payload)
    assert create_res.status_code == 201
    person_data = create_res.json()

    # Validate against Person response schema
    person_obj = s.Person.model_validate(person_data)
    assert person_obj.status == "pending"
    assert person_obj.first_name == "Eleanor"
    assert person_obj.contact.email == "eleanor.vane@example.com"
    person_id = person_obj.id

    # 2. Get person
    get_res = client.get(f"{BASE_PATH}/people/{person_id}", headers=headers_a)
    assert get_res.status_code == 200
    assert get_res.json()["id"] == person_id

    # 3. Initial status history check (must not leak previous_status)
    history_res = client.get(f"{BASE_PATH}/people/{person_id}/status", headers=headers_a)
    assert history_res.status_code == 200
    history = history_res.json()
    assert len(history) == 1
    # Verify strict schema validation passes and previous_status is not present
    hist_entry = s.StatusHistoryEntry.model_validate(history[0])
    assert hist_entry.status == "pending"
    assert "previous_status" not in history[0]

    # 4. Patch person profile fields
    patch_res = client.patch(
        f"{BASE_PATH}/people/{person_id}",
        headers=headers_a,
        json={"preferred_name": "El"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["preferred_name"] == "El"

    # 5. Duplicate identity_number conflict (409)
    dup_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={
            "first_name": "Imposter",
            "last_name": "Vane",
            "identity_number": "NAT-EL-5501",
        },
    )
    assert dup_res.status_code == 409
    conflict_err = s.ConflictError.model_validate(dup_res.json()["detail"])
    assert conflict_err.code == "duplicate_identity_number"

    # 6. Change status
    status_change_res = client.put(
        f"{BASE_PATH}/people/{person_id}/status",
        headers=headers_a,
        json={"status": "active", "reason": "Matriculation completed"},
    )
    assert status_change_res.status_code == 200
    assert status_change_res.json()["status"] == "active"

    # 7. Unchanged status returns 422 RuleError
    unchanged_res = client.put(
        f"{BASE_PATH}/people/{person_id}/status",
        headers=headers_a,
        json={"status": "active", "reason": "Attempting redundant change"},
    )
    assert unchanged_res.status_code == 422
    rule_err = s.RuleError.model_validate(unchanged_res.json()["detail"])
    assert rule_err.code == "status_unchanged"

    # Verify history now has 2 entries, ordered newest first
    history_res2 = client.get(f"{BASE_PATH}/people/{person_id}/status", headers=headers_a)
    assert len(history_res2.json()) == 2
    assert history_res2.json()[0]["status"] == "active"
    assert history_res2.json()[1]["status"] == "pending"


# =====================================================================
# 5. Search, Filter, & Pagination Tests
# =====================================================================


def test_people_search_and_pagination(client, headers_a):
    # Create multiple records
    for i in range(3):
        client.post(
            f"{BASE_PATH}/people",
            headers=headers_a,
            json={
                "first_name": f"Student{i}",
                "last_name": "SearchTest",
                "identity_number": f"NAT-SEARCH-{i}",
                "contact": {"email": f"student{i}@search.edu"},
            },
        )

    # Search by q
    res_q = client.get(f"{BASE_PATH}/people?q=SearchTest", headers=headers_a)
    assert res_q.status_code == 200
    page_data = s.PersonPage.model_validate(res_q.json())
    assert page_data.total >= 3

    # Exact identity_number filter
    res_id = client.get(f"{BASE_PATH}/people?identity_number=NAT-SEARCH-1", headers=headers_a)
    assert res_id.status_code == 200
    assert len(res_id.json()["items"]) == 1
    assert res_id.json()["items"][0]["identity_number"] == "NAT-SEARCH-1"

    # Comma-separated status filtering
    res_status = client.get(f"{BASE_PATH}/people?status=pending,active", headers=headers_a)
    assert res_status.status_code == 200
    assert all(p["status"] in ("pending", "active") for p in res_status.json()["items"])

    # Pagination bounds
    res_paged = client.get(f"{BASE_PATH}/people?page=1&page_size=2", headers=headers_a)
    assert res_paged.status_code == 200
    assert len(res_paged.json()["items"]) <= 2
    assert res_paged.json()["page"] == 1
    assert res_paged.json()["page_size"] == 2


# =====================================================================
# 6. Document Attach, List, & Delete
# =====================================================================


def test_document_lifecycle(client, headers_a):
    create_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "Doc", "last_name": "Owner"},
    )
    person_id = create_res.json()["id"]

    # Attach document
    doc_payload = {
        "type": "identity_proof",
        "document_id": "platform-doc-uuid-99",
        "label": "Passport scan",
    }
    attach_res = client.post(
        f"{BASE_PATH}/people/{person_id}/documents",
        headers=headers_a,
        json=doc_payload,
    )
    assert attach_res.status_code == 201
    doc_data = attach_res.json()
    doc_obj = s.PersonDocument.model_validate(doc_data)
    assert doc_obj.document_id == "platform-doc-uuid-99"
    assert doc_obj.label == "Passport scan"

    # List documents
    list_res = client.get(f"{BASE_PATH}/people/{person_id}/documents", headers=headers_a)
    assert list_res.status_code == 200
    assert len(list_res.json()) == 1

    # Delete document (204 No Content)
    # The path takes the PersonDocument reference id, not the platform document id
    del_by_platform_id = client.delete(
        f"{BASE_PATH}/people/{person_id}/documents/platform-doc-uuid-99",
        headers=headers_a,
    )
    assert del_by_platform_id.status_code == 404
    del_res = client.delete(
        f"{BASE_PATH}/people/{person_id}/documents/{doc_obj.id}",
        headers=headers_a,
    )
    assert del_res.status_code == 204

    # Verify document is gone
    list_after = client.get(f"{BASE_PATH}/people/{person_id}/documents", headers=headers_a)
    assert len(list_after.json()) == 0

    # Deleting non-existent document yields 404
    del_404 = client.delete(
        f"{BASE_PATH}/people/{person_id}/documents/non-existent-uuid",
        headers=headers_a,
    )
    assert del_404.status_code == 404


# =====================================================================
# 7. Identity Card Issuance, Conflict, & Revocation
# =====================================================================


def test_id_card_lifecycle(client, headers_a):
    create_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "Card", "last_name": "Holder"},
    )
    person_id = create_res.json()["id"]

    # 1. Issue card (with optional expires_at)
    issue_res = client.post(
        f"{BASE_PATH}/people/{person_id}/id-cards",
        headers=headers_a,
        json={"expires_at": "2028-06-30"},
    )
    assert issue_res.status_code == 201
    card_data = issue_res.json()
    card_obj = s.IdentityCard.model_validate(card_data)
    assert card_obj.status == "issued"
    assert card_obj.card_number.startswith("IDC-")
    assert card_obj.expires_at.isoformat() == "2028-06-30"
    card_id = card_obj.id

    # 2. Cannot issue another card while active card exists (409)
    conflict_res = client.post(
        f"{BASE_PATH}/people/{person_id}/id-cards",
        headers=headers_a,
        json={},
    )
    assert conflict_res.status_code == 409
    err = s.ConflictError.model_validate(conflict_res.json()["detail"])
    assert err.code == "active_card_exists"

    # 3. List cards
    cards_list = client.get(f"{BASE_PATH}/people/{person_id}/id-cards", headers=headers_a)
    assert len(cards_list.json()) == 1

    # 4. Revoke card
    revoke_res = client.post(
        f"{BASE_PATH}/id-cards/{card_id}/revoke",
        headers=headers_a,
        json={"reason": "Card reported lost"},
    )
    assert revoke_res.status_code == 200
    revoked_card = s.IdentityCard.model_validate(revoke_res.json())
    assert revoked_card.status == "revoked"
    assert revoked_card.revoked_reason == "Card reported lost"

    # 5. Revoking already revoked card yields 409 card_not_active
    revoke_again = client.post(
        f"{BASE_PATH}/id-cards/{card_id}/revoke",
        headers=headers_a,
        json={"reason": "Trying again"},
    )
    assert revoke_again.status_code == 409
    err_revoked = s.ConflictError.model_validate(revoke_again.json()["detail"])
    assert err_revoked.code == "card_not_active"

    # 6. Now can issue a replacement card without body
    replace_res = client.post(
        f"{BASE_PATH}/people/{person_id}/id-cards",
        headers=headers_a,
    )
    assert replace_res.status_code == 201
    assert replace_res.json()["status"] == "issued"


# =====================================================================
# 8. Multi-Tenant Isolation
# =====================================================================


def test_multi_tenant_isolation(client, headers_a, headers_b):
    # Org A creates a person
    res_a = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={
            "first_name": "TenantA",
            "last_name": "Person",
            "identity_number": "SHARED-ID-9999",
            "contact": {"email": "tenanta@org-a.com"},
        },
    )
    person_a_id = res_a.json()["id"]

    # Org B cannot see Person A
    get_b = client.get(f"{BASE_PATH}/people/{person_a_id}", headers=headers_b)
    assert get_b.status_code == 404

    # Org B cannot update Person A
    patch_b = client.patch(
        f"{BASE_PATH}/people/{person_a_id}",
        headers=headers_b,
        json={"preferred_name": "Infiltrator"},
    )
    assert patch_b.status_code == 404

    # Org B cannot see status history of Person A
    hist_b = client.get(f"{BASE_PATH}/people/{person_a_id}/status", headers=headers_b)
    assert hist_b.status_code == 404

    # Org B cannot change status of Person A
    status_b = client.put(
        f"{BASE_PATH}/people/{person_a_id}/status",
        headers=headers_b,
        json={"status": "active", "reason": "Attack"},
    )
    assert status_b.status_code == 404

    # Org B cannot attach document to Person A
    doc_b = client.post(
        f"{BASE_PATH}/people/{person_a_id}/documents",
        headers=headers_b,
        json={"type": "address_proof", "document_id": "doc-b-1"},
    )
    assert doc_b.status_code == 404

    # Org B cannot issue ID card for Person A
    card_b = client.post(
        f"{BASE_PATH}/people/{person_a_id}/id-cards",
        headers=headers_b,
        json={},
    )
    assert card_b.status_code == 404

    # Org B can use the same identity_number (uniqueness is org-scoped)
    res_b = client.post(
        f"{BASE_PATH}/people",
        headers=headers_b,
        json={
            "first_name": "TenantB",
            "last_name": "Person",
            "identity_number": "SHARED-ID-9999",
            "contact": {"email": "tenantb@org-b.com"},
        },
    )
    assert res_b.status_code == 201
    assert res_b.json()["identity_number"] == "SHARED-ID-9999"


# =====================================================================
# 9. Transactional Outbox & Event Contract Verification
# =====================================================================


def test_transactional_outbox_events(client):
    from eos_core.db import new_id

    org_id = f"org-events-{new_id()[:8]}"
    headers = make_auth_headers(
        user_id="user-staff-events",
        organisation_id=org_id,
        roles=[REGISTRAR],
    )

    # 1. Person created with contact email -> event is published
    res_with_email = client.post(
        f"{BASE_PATH}/people",
        headers=headers,
        json={
            "first_name": "Event",
            "last_name": "Tester",
            "contact": {"email": "event.tester@example.com"},
        },
    )
    person_with_email_id = res_with_email.json()["id"]

    events = _get_outbox_events(org_id, "student-information.person.created")
    matching = [e for e in events if e.get("person_id") == person_with_email_id]
    assert len(matching) == 1
    assert matching[0]["email"] == "event.tester@example.com"

    # 2. Person created WITHOUT contact email -> event is still published, email null (contracts/events.yaml)
    res_no_email = client.post(
        f"{BASE_PATH}/people",
        headers=headers,
        json={
            "first_name": "NoEmail",
            "last_name": "Tester",
            "contact": {"phone": "+1-555-4321"},
        },
    )
    person_no_email_id = res_no_email.json()["id"]

    events_after = _get_outbox_events(org_id, "student-information.person.created")
    matching_no_email = [e for e in events_after if e.get("person_id") == person_no_email_id]
    assert len(matching_no_email) == 1
    assert matching_no_email[0]["email"] is None

    # 3. Status changed event
    client.put(
        f"{BASE_PATH}/people/{person_with_email_id}/status",
        headers=headers,
        json={"status": "active", "reason": "Admitted"},
    )
    status_events = _get_outbox_events(org_id, "student-information.person.status-changed")
    matching_status = [e for e in status_events if e.get("person_id") == person_with_email_id]
    assert len(matching_status) == 1
    assert matching_status[0]["status"] == "active"
    assert matching_status[0]["previous_status"] == "pending"

    # 4. ID card issued event
    card_res = client.post(
        f"{BASE_PATH}/people/{person_with_email_id}/id-cards",
        headers=headers,
        json={},
    )
    card_id = card_res.json()["id"]

    card_issued_events = _get_outbox_events(org_id, "student-information.id-card.issued")
    matching_card_issued = [e for e in card_issued_events if e.get("card_id") == card_id]
    assert len(matching_card_issued) == 1

    # 5. ID card revoked event
    client.post(
        f"{BASE_PATH}/id-cards/{card_id}/revoke",
        headers=headers,
        json={"reason": "Graduated early"},
    )
    card_revoked_events = _get_outbox_events(org_id, "student-information.id-card.revoked")
    matching_card_revoked = [e for e in card_revoked_events if e.get("card_id") == card_id]
    assert len(matching_card_revoked) == 1
    assert matching_card_revoked[0]["reason"] == "Graduated early"
