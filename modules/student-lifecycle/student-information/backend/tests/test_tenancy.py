"""Cross-tenant isolation tests for student-information.

Enforces Module Standard Rule 11:
- Uses eos_testing.tenancy.assert_no_cross_tenant_leak
- Proves one organisation never reads, mutates, or deletes another organisation's rows
- Confirms 404 Not Found responses rather than leaking existence
- Validates that partial unique constraints (identity_number) are strictly scoped per organisation
"""

from __future__ import annotations

from datetime import timedelta

import jwt
from eos_core.db import new_id, utcnow
from eos_core.settings import settings
from eos_testing import assert_no_cross_tenant_leak

BASE_PATH = "/api/v1/student-information"
ALL_PERMISSIONS = {
    "student-information:person:read",
    "student-information:person:write",
    "student-information:status:manage",
    "student-information:document:manage",
    "student-information:id-card:manage",
}


def mint_token(
    *,
    user_id: str = "test-user-1",
    organisation_id: str | None = None,
    roles: list[str] | None = None,
    perms: list[str] | set[str] | None = None,
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
    if perms is not None:
        payload["perms"] = list(perms)
    return jwt.encode(payload, secret or settings.jwt_secret, algorithm="HS256")


def make_auth_headers(
    *,
    user_id: str = "test-user-1",
    organisation_id: str | None = None,
    roles: list[str] | None = None,
    perms: list[str] | set[str] | None = None,
    sa: bool = False,
    secret: str | None = None,
) -> dict[str, str]:
    token = mint_token(
        user_id=user_id,
        organisation_id=organisation_id,
        roles=roles,
        perms=perms,
        sa=sa,
        secret=secret,
    )
    return {"Authorization": f"Bearer {token}"}


def _seed_org(client, org_id: str) -> dict:
    headers = make_auth_headers(
        user_id=f"user-{org_id[:8]}",
        organisation_id=org_id,
        perms=ALL_PERMISSIONS,
    )
    token = mint_token(
        user_id=f"user-{org_id[:8]}",
        organisation_id=org_id,
        perms=ALL_PERMISSIONS,
    )

    # Create a person
    person_res = client.post(
        f"{BASE_PATH}/people",
        headers=headers,
        json={
            "first_name": "Tenant",
            "last_name": f"Person-{org_id[:6]}",
            "identity_number": f"NAT-{org_id[:8]}",
            "contact": {"email": f"student@{org_id[:8]}.edu"},
        },
    )
    assert person_res.status_code == 201, person_res.text
    person = person_res.json()

    # Attach a document
    doc_res = client.post(
        f"{BASE_PATH}/people/{person['id']}/documents",
        headers=headers,
        json={"type": "identity_proof", "document_id": f"doc-{org_id[:8]}"},
    )
    assert doc_res.status_code == 201
    doc = doc_res.json()

    # Issue an ID card
    card_res = client.post(
        f"{BASE_PATH}/people/{person['id']}/id-cards",
        headers=headers,
        json={},
    )
    assert card_res.status_code == 201
    card = card_res.json()

    return {
        "org_id": org_id,
        "token": token,
        "headers": headers,
        "person_id": person["id"],
        "document_id": doc["document_id"],
        "card_id": card["id"],
    }


def test_eos_testing_assert_no_cross_tenant_leak(client):
    """Executes eos_testing.assert_no_cross_tenant_leak on /people route."""
    org_a_id = f"org-leak-a-{new_id()[:8]}"
    org_b_id = f"org-leak-b-{new_id()[:8]}"

    a = _seed_org(client, org_a_id)
    b = _seed_org(client, org_b_id)

    # Use the official eos_testing cross-tenant leak assertion
    assert_no_cross_tenant_leak(
        client,
        f"{BASE_PATH}/people",
        a["token"],
        b["token"],
        id_field="organisation_id",
    )


def test_cross_tenant_reads_return_404(client):
    """Verify Organization B cannot read any resource belonging to Organization A."""
    a = _seed_org(client, f"org-read-a-{new_id()[:8]}")
    b = _seed_org(client, f"org-read-b-{new_id()[:8]}")

    person_a = a["person_id"]

    # Person get
    assert client.get(f"{BASE_PATH}/people/{person_a}", headers=b["headers"]).status_code == 404

    # Status history get
    assert client.get(f"{BASE_PATH}/people/{person_a}/status", headers=b["headers"]).status_code == 404

    # Documents list
    assert client.get(f"{BASE_PATH}/people/{person_a}/documents", headers=b["headers"]).status_code == 404

    # ID cards list
    assert client.get(f"{BASE_PATH}/people/{person_a}/id-cards", headers=b["headers"]).status_code == 404


def test_cross_tenant_writes_and_deletes_return_404(client):
    """Verify Organization B cannot modify or delete Organization A's resources."""
    a = _seed_org(client, f"org-write-a-{new_id()[:8]}")
    b = _seed_org(client, f"org-write-b-{new_id()[:8]}")

    person_a = a["person_id"]
    doc_a = a["document_id"]
    card_a = a["card_id"]

    # Update person
    assert (
        client.patch(f"{BASE_PATH}/people/{person_a}", headers=b["headers"], json={"first_name": "Hacked"}).status_code
        == 404
    )

    # Change status
    assert (
        client.put(
            f"{BASE_PATH}/people/{person_a}/status",
            headers=b["headers"],
            json={"status": "suspended", "reason": "Unauthorized"},
        ).status_code
        == 404
    )

    # Attach document
    assert (
        client.post(
            f"{BASE_PATH}/people/{person_a}/documents",
            headers=b["headers"],
            json={"type": "address_proof", "document_id": "malicious-doc"},
        ).status_code
        == 404
    )

    # Delete document
    assert (
        client.delete(
            f"{BASE_PATH}/people/{person_a}/documents/{doc_a}",
            headers=b["headers"],
        ).status_code
        == 404
    )

    # Issue ID card
    assert (
        client.post(
            f"{BASE_PATH}/people/{person_a}/id-cards",
            headers=b["headers"],
            json={},
        ).status_code
        == 404
    )

    # Revoke ID card
    assert (
        client.post(
            f"{BASE_PATH}/id-cards/{card_a}/revoke",
            headers=b["headers"],
            json={"reason": "Malicious revoke"},
        ).status_code
        == 404
    )


def test_identity_number_uniqueness_strictly_scoped_by_tenant(client):
    """Same identity_number can exist across different organisations without collision."""
    shared_identity = f"SHARED-NAT-ID-{new_id()[:8]}"

    org_a = f"org-iso-a-{new_id()[:8]}"
    org_b = f"org-iso-b-{new_id()[:8]}"

    headers_a = make_auth_headers(organisation_id=org_a, perms=ALL_PERMISSIONS)
    headers_b = make_auth_headers(organisation_id=org_b, perms=ALL_PERMISSIONS)

    # Org A creates person with shared_identity
    res_a1 = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "OrgA", "last_name": "Student1", "identity_number": shared_identity},
    )
    assert res_a1.status_code == 201

    # Org B creates person with the EXACT SAME shared_identity
    res_b1 = client.post(
        f"{BASE_PATH}/people",
        headers=headers_b,
        json={"first_name": "OrgB", "last_name": "Student1", "identity_number": shared_identity},
    )
    assert res_b1.status_code == 201
    assert res_b1.json()["identity_number"] == shared_identity

    # Within Org A, duplicate identity_number is rejected (409)
    res_a2 = client.post(
        f"{BASE_PATH}/people",
        headers=headers_a,
        json={"first_name": "OrgA", "last_name": "Student2", "identity_number": shared_identity},
    )
    assert res_a2.status_code == 409
    assert res_a2.json()["detail"]["code"] == "duplicate_identity_number"
