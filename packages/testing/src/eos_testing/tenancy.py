"""Helpers every module's test suite uses to prove it does not leak across organisations."""

from __future__ import annotations


def register_and_login(
    client,
    *,
    slug: str,
    academy_type: str = "sports-college",
    email: str | None = None,
    password: str = "Passw0rd!x",
    super_admin: tuple[str, str] | None = None,
) -> dict:
    """Register an organisation, verify it with the dev-mode token, log the admin in. Returns {org, token}.

    The verification token comes from the register response, which carries it only with EOS_DEV_MODE=true. Since
    #361 the verification mail goes through platform/notification, which this package may not import (packages
    never depend on platform services), so there is no other place to read it from."""
    email = email or f"admin@{slug}.example.com"
    r = client.post(
        "/api/v1/tenancy/register",
        json={
            "organisation_name": slug.replace("-", " ").title(),
            "slug": slug,
            "academy_type": academy_type,
            "admin": {"name": "Admin", "email": email, "password": password},
            "accepted_terms": True,
        },
    )
    assert r.status_code == 201, r.text
    org = r.json()
    token = org.get("verification_token")
    if not token:
        raise AssertionError(
            "register_and_login needs EOS_DEV_MODE=true: the register response returns the verification token only "
            "in dev mode, and since #361 the mail goes through platform/notification, which eos_testing cannot read"
        )
    v = client.post("/api/v1/tenancy/register/verify", json={"token": token})
    assert v.status_code == 200, v.text
    if v.json()["status"] == "pending_approval":
        if not super_admin:
            raise AssertionError(
                "organisation needs super admin approval; pass super_admin=(email, password) or set TENANCY_AUTO_APPROVE=true"
            )
        r = client.post("/api/v1/identity/auth/login", json={"email": super_admin[0], "password": super_admin[1]})
        assert r.status_code == 200, r.text
        a = client.post(
            f"/api/v1/tenancy/admin/organisations/{org['id']}/approve",
            json={"reason": "test"},
            headers=auth(r.json()["token"]),
        )
        assert a.status_code == 200, a.text
    r = client.post(
        "/api/v1/identity/auth/login", json={"email": email, "password": password, "organisation_slug": slug}
    )
    assert r.status_code == 200, r.text
    return {"org": org, "token": r.json()["token"], "email": email, "password": password}


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def assert_no_cross_tenant_leak(
    client, path: str, token_a: str, token_b: str, id_field: str = "organisation_id"
) -> None:
    """GET `path` as A and as B; every returned row must belong to the caller and the sets must not overlap."""
    ra, rb = client.get(path, headers=auth(token_a)), client.get(path, headers=auth(token_b))
    assert ra.status_code == 200 and rb.status_code == 200, (ra.text, rb.text)
    rows_a, rows_b = _rows(ra.json()), _rows(rb.json())
    orgs_a, orgs_b = {r.get(id_field) for r in rows_a}, {r.get(id_field) for r in rows_b}
    assert len(orgs_a) <= 1 and len(orgs_b) <= 1, (orgs_a, orgs_b)
    assert not (orgs_a & orgs_b), f"{path} returned the same organisation to two tenants"
    ids_a, ids_b = {r.get("id") for r in rows_a}, {r.get("id") for r in rows_b}
    assert not (ids_a & ids_b), f"{path} returned the same rows to two tenants"


def _rows(body):
    if isinstance(body, list):
        return body
    if isinstance(body, dict):
        return body.get("items") or [body]
    return []
