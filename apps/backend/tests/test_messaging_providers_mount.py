"""messaging-providers is listed under integrations in config/modules.enabled.yaml. Its routes are platform-level:
only the super admin, who has no organisation, may call them, so the entitlement gate must let them through to
the route's own permission check (eos_core.entitlement.PLATFORM_MODULES)."""

from eos_testing import register_and_login
from eos_testing.tenancy import auth

PROVIDERS = "/api/v1/messaging-providers/providers"


def _super_admin(client) -> dict:
    r = client.post(
        "/api/v1/identity/auth/login", json={"email": "root@platform.example.com", "password": "RootPassw0rd!"}
    )
    assert r.status_code == 200, r.text
    return auth(r.json()["token"])


def test_the_adapter_is_mounted(client):
    assert "messaging-providers" in client.get("/api/v1/health").json()["modules"]


def test_the_super_admin_reaches_the_provider_list_through_the_gate(client):
    r = client.get(PROVIDERS, headers=_super_admin(client))
    assert r.status_code == 200, r.text
    assert [p["id"] for p in r.json()["items"]] == ["smtp"]


def test_an_organisation_admin_is_refused_by_the_route_not_the_plan(client):
    a = register_and_login(client, slug="mp-mount", academy_type="music-academy")
    r = client.get(PROVIDERS, headers=auth(a["token"]))
    assert r.status_code == 403 and r.json().get("code") != "module_not_entitled", r.text


def test_no_token_is_refused(client):
    assert client.get(PROVIDERS).status_code == 401
