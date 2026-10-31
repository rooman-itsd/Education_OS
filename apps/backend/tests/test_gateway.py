"""platform/api-gateway in the host: security headers on every response, rate limits per address and per
organisation with 429 + Retry-After, and the plan's user limit enforced where users are created."""

from eos_backend.main import create_app
from eos_testing import register_and_login
from eos_testing.tenancy import auth
from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from fastapi.testclient import TestClient

ME = "/api/v1/identity/auth/me"


def test_every_response_carries_the_security_headers(client):
    r = client.get("/api/v1/health")
    assert r.status_code == 200
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert r.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
    assert r.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in r.headers  # the test client speaks plain http
    r = client.get("/api/v1/health", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    # the gate's refusal and a 404 carry them too
    assert client.get("/api/v1/fees-accounts/ping").headers["x-frame-options"] == "DENY"
    assert client.get("/api/v1/no-such-module/x").headers["x-content-type-options"] == "nosniff"


def test_a_page_with_its_own_csp_keeps_it_through_the_host(monkeypatch):
    """Like the SBI ePay hand-off page: the route's policies win over the host's JSON default and no-referrer
    (SecurityHeaders only fills in headers a response lacks)."""
    monkeypatch.setenv("EOS_RATE_LIMIT_ENABLED", "false")
    page = APIRouter()
    policy = "default-src 'none'; script-src 'nonce-x'; form-action 'self' https:"

    @page.get("/test-handoff")
    def handoff():
        return HTMLResponse(
            "<form></form>",
            headers={"Content-Security-Policy": policy, "Referrer-Policy": "strict-origin-when-cross-origin"},
        )

    # mounted under a platform prefix, which the entitlement gate lets through without a token
    r = TestClient(create_app(extra_routers={"identity": page})).get("/api/v1/identity/test-handoff")
    assert r.status_code == 200
    assert r.headers["content-security-policy"] == policy and r.headers["x-frame-options"] == "DENY"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"


def test_the_host_rate_limits_per_address_and_exempts_health(monkeypatch):
    monkeypatch.setenv("EOS_RATE_LIMIT_ENABLED", "true")
    monkeypatch.setenv("EOS_RATE_LIMIT_IP_PER_MINUTE", "3")
    monkeypatch.setenv("EOS_RATE_LIMIT_IP_BURST", "3")
    app = create_app()  # reads the limits now; no lifespan needed for these routes
    a = TestClient(app, client=("198.51.100.7", 1))
    b = TestClient(app, client=("198.51.100.8", 1))
    for _ in range(5):
        assert a.get("/api/v1/health").status_code == 200
    for _ in range(3):
        assert a.get(ME).status_code == 401  # counted, whatever the route answers
    r = a.get(ME, headers={"Origin": "http://localhost:5173"})
    assert r.status_code == 429, r.text
    assert r.headers["retry-after"] == "20"  # 3 a minute: one token every 20 s
    assert r.json()["code"] == "rate_limited" and r.json()["scope"] == "ip" and r.json()["retry_after"] == 20
    assert r.headers["access-control-allow-origin"] == "http://localhost:5173"  # a browser may read it
    assert r.headers["x-frame-options"] == "DENY"
    assert b.get(ME).status_code == 401  # another address, its own bucket
    # behind the proxy (loopback is trusted by default), each forwarded client is its own bucket
    proxied = TestClient(app, client=("127.0.0.1", 1))
    for _ in range(3):
        assert proxied.get(ME, headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 401
    assert proxied.get(ME, headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 429
    assert proxied.get(ME, headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 401


def test_the_plan_user_limit_refuses_the_user_past_it_and_usage_shows_it(client):
    a = register_and_login(client, slug="limits-org", academy_type="music-academy")
    org, admin = a["org"]["id"], auth(a["token"])
    root = client.post(
        "/api/v1/identity/auth/login", json={"email": "root@platform.example.com", "password": "RootPassw0rd!"}
    )
    sa = auth(root.json()["token"])
    r = client.put(
        "/api/v1/billing/admin/plans/tiny",
        json={"id": "tiny", "title": "Tiny", "suites": ["student-lifecycle"], "limits": {"users": 2}},
        headers=sa,
    )
    assert r.status_code == 200, r.text
    r = client.put(f"/api/v1/billing/admin/subscriptions/{org}", json={"plan": "tiny", "reason": "test"}, headers=sa)
    assert r.status_code == 200, r.text

    usage = client.get("/api/v1/billing/usage", headers=admin).json()
    assert usage == {
        "plan": "tiny",
        "limits": {"users": 2},
        "usage": {"users": 1, "students": None, "storage_gb": None},
        "at_limit": [],
    }
    body = {"email": "two@limits-org.example.com", "name": "Two", "password": "Passw0rd!x", "roles": ["student"]}
    assert client.post("/api/v1/identity/users", json=body, headers=admin).status_code == 201
    r = client.post("/api/v1/identity/users", json={**body, "email": "three@limits-org.example.com"}, headers=admin)
    assert r.status_code == 409, r.text
    assert r.json() == {
        "detail": "the plan allows 2 users; 2 are active",
        "code": "plan_limit_reached",
        "limit": "users",
        "allowed": 2,
        "used": 2,
    }
    usage = client.get("/api/v1/billing/usage", headers=admin).json()
    assert usage["usage"]["users"] == 2 and usage["at_limit"] == ["users"]
    assert len(client.get("/api/v1/identity/users", headers=admin).json()) == 2  # nothing was written
    # another organisation on the trial plan (25 users) is not affected
    b = register_and_login(client, slug="limits-other", academy_type="music-academy")
    assert client.get("/api/v1/billing/usage", headers=auth(b["token"])).json()["limits"]["users"] == 25


def test_start_up_warns_once_when_trusted_proxies_is_unset_outside_dev_mode(monkeypatch, caplog):
    import logging
    from dataclasses import replace

    from eos_backend import main

    monkeypatch.setenv("EOS_RATE_LIMIT_ENABLED", "true")
    monkeypatch.delenv("EOS_TRUSTED_PROXIES", raising=False)
    monkeypatch.setattr(main, "settings", replace(main.settings, dev_mode=False))
    with caplog.at_level(logging.WARNING, logger="eos.api"):
        create_app()
    assert [r.getMessage() for r in caplog.records if "EOS_TRUSTED_PROXIES is not set" in r.getMessage()] != []
    assert sum("EOS_TRUSTED_PROXIES is not set" in r.getMessage() for r in caplog.records) == 1

    caplog.clear()
    monkeypatch.setenv("EOS_TRUSTED_PROXIES", "10.0.0.5")  # named: no warning
    with caplog.at_level(logging.WARNING, logger="eos.api"):
        create_app()
    assert not any("EOS_TRUSTED_PROXIES" in r.getMessage() for r in caplog.records)

    caplog.clear()
    monkeypatch.delenv("EOS_TRUSTED_PROXIES")
    monkeypatch.setattr(main, "settings", replace(main.settings, dev_mode=True))  # dev mode: quiet
    with caplog.at_level(logging.WARNING, logger="eos.api"):
        create_app()
    assert not any("EOS_TRUSTED_PROXIES" in r.getMessage() for r in caplog.records)


def test_the_gate_reuses_the_token_the_limiter_decoded(client, monkeypatch):
    """Second review of PR 363, point 8: one decode per request, shared through request.state."""
    from eos_api_gateway.api import claims

    a = register_and_login(client, slug="decode-once", academy_type="music-academy")
    monkeypatch.setenv("EOS_RATE_LIMIT_ENABLED", "true")
    app = create_app(extra_routers={"fees-accounts": APIRouter()})
    calls = []
    real = claims.decode

    async def counted(token):
        calls.append(token)
        return await real(token)

    monkeypatch.setattr(claims, "decode", counted)
    r = TestClient(app).get("/api/v1/fees-accounts/nothing-here", headers=auth(a["token"]))
    assert r.status_code in (403, 404), r.text  # past the limiter and the gate, whichever answers
    assert len(calls) == 1
    r = TestClient(app).get("/api/v1/fees-accounts/x", headers={"Authorization": "Bearer forged"})
    assert r.status_code == 401 and r.json()["detail"].startswith("invalid token") and len(calls) == 2
