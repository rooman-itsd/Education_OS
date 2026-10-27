"""Regressions from the review of the module PR: permissions come from catalogue roles, not a token claim;
identity numbers are normalised; one person per identity user; names cannot be blanked; q searches names and
the email only."""

from __future__ import annotations

from conftest import ADMISSIONS, BASE_PATH, NO_ACCESS, READ_ONLY, REGISTRAR, make_auth_headers
from eos_core.db import new_id


def _org_headers(role: str = REGISTRAR, org: str | None = None) -> tuple[str, dict]:
    org = org or f"org-rev-{new_id()[:8]}"
    return org, make_auth_headers(user_id=f"user-{role}-{new_id()[:6]}", organisation_id=org, roles=[role])


def _person(client, headers, **fields) -> dict:
    body = {"first_name": "Ada", "last_name": "Lovelace", **fields}
    res = client.post(f"{BASE_PATH}/people", headers=headers, json=body)
    assert res.status_code == 201, res.text
    return res.json()


def test_catalogue_roles_reach_the_module_and_a_perms_claim_does_not(client):
    """Identity issues tokens with roles only; the module must work for the roles permissions.yaml grants."""
    import jwt
    from eos_core.settings import settings

    org, registrar = _org_headers(REGISTRAR)
    person = _person(client, registrar)
    _, admissions = _org_headers(ADMISSIONS, org)
    _, management = _org_headers(READ_ONLY, org)
    _, student = _org_headers(NO_ACCESS, org)

    assert client.get(f"{BASE_PATH}/people", headers=management).status_code == 200
    assert (
        client.post(f"{BASE_PATH}/people", headers=management, json={"first_name": "x", "last_name": "y"}).status_code
        == 403
    )
    assert (
        client.post(f"{BASE_PATH}/people", headers=admissions, json={"first_name": "x", "last_name": "y"}).status_code
        == 201
    )
    assert client.get(f"{BASE_PATH}/people", headers=student).status_code == 403
    assert (
        client.put(
            f"{BASE_PATH}/people/{person['id']}/status",
            headers=admissions,
            json={"status": "active", "reason": "no"},
        ).status_code
        == 403
    )

    # A forged "perms" claim grants nothing
    claims = jwt.decode(student["Authorization"].split(" ", 1)[1], settings.jwt_secret, algorithms=["HS256"])
    claims["perms"] = ["student-information:person:read"]
    forged = {"Authorization": "Bearer " + jwt.encode(claims, settings.jwt_secret, algorithm="HS256")}
    assert client.get(f"{BASE_PATH}/people", headers=forged).status_code == 403


def test_identity_number_is_trimmed_and_empty_means_not_provided(client):
    _, headers = _org_headers()
    first = _person(client, headers, identity_number="")
    second = _person(client, headers, identity_number="   ")
    assert first["identity_number"] is None and second["identity_number"] is None

    kept = _person(client, headers, identity_number=" NAT-1 ")
    assert kept["identity_number"] == "NAT-1"
    dup = client.post(
        f"{BASE_PATH}/people", headers=headers, json={"first_name": "B", "last_name": "C", "identity_number": "NAT-1 "}
    )
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "duplicate_identity_number"

    patched = client.patch(f"{BASE_PATH}/people/{first['id']}", headers=headers, json={"identity_number": " "})
    assert patched.status_code == 200 and patched.json()["identity_number"] is None


def test_one_person_per_identity_user_and_lookup_by_user(client):
    org, headers = _org_headers()
    user_id = new_id()
    linked = _person(client, headers, identity_user_id=user_id)
    other = _person(client, headers, first_name="Bob")

    dup = client.post(
        f"{BASE_PATH}/people",
        headers=headers,
        json={"first_name": "C", "last_name": "D", "identity_user_id": user_id},
    )
    assert dup.status_code == 409 and dup.json()["detail"]["code"] == "duplicate_identity_user"
    relink = client.patch(f"{BASE_PATH}/people/{other['id']}", headers=headers, json={"identity_user_id": user_id})
    assert relink.status_code == 409 and relink.json()["detail"]["code"] == "duplicate_identity_user"
    # Re-saving the same link on the same person is not a conflict
    same = client.patch(f"{BASE_PATH}/people/{linked['id']}", headers=headers, json={"identity_user_id": user_id})
    assert same.status_code == 200

    found = client.get(f"{BASE_PATH}/people", headers=headers, params={"identity_user_id": user_id}).json()
    assert [p["id"] for p in found["items"]] == [linked["id"]]

    # Another organisation may link the same user id (unique per organisation)
    _, elsewhere = _org_headers()
    assert _person(client, elsewhere, identity_user_id=user_id)["identity_user_id"] == user_id


def test_patch_cannot_blank_a_name(client):
    _, headers = _org_headers()
    person = _person(client, headers)
    assert (
        client.patch(f"{BASE_PATH}/people/{person['id']}", headers=headers, json={"first_name": ""}).status_code == 422
    )
    assert (
        client.patch(f"{BASE_PATH}/people/{person['id']}", headers=headers, json={"last_name": ""}).status_code == 422
    )


def test_q_searches_names_and_email_only_with_literal_wildcards(client):
    _, headers = _org_headers()
    ada = _person(client, headers, contact={"email": "ada@example.org", "phone": "555-0199", "address": "Elm Street"})
    _person(client, headers, first_name="Grace", last_name="Hopper", contact={"email": "grace@example.org"})

    def ids(q: str) -> list[str]:
        return [p["id"] for p in client.get(f"{BASE_PATH}/people", headers=headers, params={"q": q}).json()["items"]]

    assert ids("ada@") == [ada["id"]]
    assert ids("ADA") == [ada["id"]]
    assert ids("Elm Street") == []
    assert ids("555-0199") == []
    assert ids("%") == []
    assert ids("_") == []
