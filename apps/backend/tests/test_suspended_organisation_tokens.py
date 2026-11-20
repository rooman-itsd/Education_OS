"""Security review N2 (#671): suspending an organisation takes effect on the next request, not when its tokens
expire. Sign-in was already refused; a token issued before the suspension kept working on every platform service
(identity, audit, billing, ...) for up to 12 hours. The gate now refuses it there too, with the same 403
`organisation_inactive` a feature module gives, and reactivating gives the same token its access back."""

from eos_testing import register_and_login
from eos_testing.tenancy import auth

SA = {"email": "root@platform.example.com", "password": "RootPassw0rd!"}


def _super_admin(client) -> dict:
    r = client.post("/api/v1/identity/auth/login", json=SA)
    assert r.status_code == 200, r.text
    return auth(r.json()["token"])


def _set_status(client, sa: dict, org_id: str, status: str) -> None:
    r = client.put(
        f"/api/v1/tenancy/admin/organisations/{org_id}/status", json={"status": status, "reason": "N2"}, headers=sa
    )
    assert r.status_code == 200 and r.json()["status"] == status, r.text


def _refused(r) -> bool:
    return r.status_code == 403 and r.json()["code"] == "organisation_inactive"


def test_a_suspended_organisations_old_token_is_refused_on_the_next_request_and_reactivation_restores_it(client):
    a = register_and_login(client, slug="n2-suspend", academy_type="dance-academy")
    h, org_id, sa = auth(a["token"]), a["org"]["id"], _super_admin(client)
    reads = ["/api/v1/identity/users", "/api/v1/audit/records", "/api/v1/identity/auth/me", "/api/v1/lms/ping"]
    for path in reads:
        assert client.get(path, headers=h).status_code == 200, path

    _set_status(client, sa, org_id, "suspended")
    for path in reads:
        r = client.get(path, headers=h)
        assert _refused(r), (path, r.status_code, r.text)
        assert r.json()["detail"] == "organisation is suspended"
    assert _refused(client.post("/api/v1/billing/subscription/upgrade", json={"plan": "standard"}, headers=h))
    assert _refused(client.get("/api/v1/billing/subscription", headers=h))
    # the super admin's own token carries no organisation and is never refused
    assert client.get(f"/api/v1/tenancy/admin/organisations/{org_id}", headers=sa).status_code == 200

    _set_status(client, sa, org_id, "active")
    for path in reads:
        assert client.get(path, headers=h).status_code == 200, path
    # the upgrade attempted while suspended never reached billing
    assert client.get("/api/v1/billing/subscription", headers=h).json()["plan"] == "trial"


def test_an_impersonation_token_into_a_suspended_organisation_is_refused(client):
    a = register_and_login(client, slug="n2-imp", academy_type="dance-academy")
    org_id, sa = a["org"]["id"], _super_admin(client)
    user_id = client.get("/api/v1/identity/users", headers=auth(a["token"])).json()[0]["id"]
    r = client.post(
        f"/api/v1/tenancy/admin/organisations/{org_id}/impersonate",
        json={"user_id": user_id, "reason": "support"},
        headers=sa,
    )
    assert r.status_code == 201, r.text
    imp = auth(r.json()["token"])
    assert client.get("/api/v1/identity/users", headers=imp).status_code == 200
    _set_status(client, sa, org_id, "suspended")
    assert _refused(client.get("/api/v1/identity/users", headers=imp))
    assert _refused(client.get("/api/v1/lms/ping", headers=imp))


def test_tokens_without_an_organisation_and_bad_tokens_reach_the_platform_routes_own_checks(client):
    # no organisation (super admin): passes; no token or a bad one: the route answers 401 as before
    assert client.get("/api/v1/tenancy/admin/organisations", headers=_super_admin(client)).status_code == 200
    assert client.get("/api/v1/identity/users").status_code == 401
    assert client.get("/api/v1/identity/users", headers=auth("not-a-jwt")).status_code == 401
    assert client.get("/api/v1/billing/plans").status_code == 200  # public route, no token
