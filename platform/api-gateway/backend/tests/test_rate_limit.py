"""Buckets per client IP, per organisation (bearer token's `org`) and the stricter one for sign-in and sign-up;
429 with Retry-After and a JSON body; health exempt; X-Forwarded-For believed only from a trusted proxy."""

from conftest import PEER, FakeClock, make_app
from eos_api_gateway import GatewaySettings
from eos_api_gateway.application.limiter import RateLimiter
from eos_api_gateway.domain.bucket import Limit
from eos_api_gateway.infrastructure import MemoryStore
from eos_core.security import create_token
from fastapi.testclient import TestClient


def bearer(org: str | None) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user_id='u1', organisation_id=org, roles=['student'])}"}


def test_ip_bucket_refuses_past_the_burst_and_refills_with_time(client, clock):
    for _ in range(3):
        assert client.get("/api/v1/things").status_code == 200
    r = client.get("/api/v1/things")
    assert r.status_code == 429
    assert r.headers["retry-after"] == "1"
    assert r.json() == {
        "detail": "too many requests for this address; retry after 1 seconds",
        "code": "rate_limited",
        "scope": "ip",
        "retry_after": 1,
    }
    clock.advance(1.0)  # 60 per minute: one token a second
    assert client.get("/api/v1/things").status_code == 200
    assert client.get("/api/v1/things").status_code == 429


def test_retry_after_grows_with_the_shortfall(settings, clock):
    client = TestClient(make_app(settings, clock), client=PEER)
    for _ in range(3):
        client.get("/api/v1/things")
    clock.advance(0.2)  # 0.2 tokens back: 0.8 s to the next one, reported as 1
    assert client.get("/api/v1/things").headers["retry-after"] == "1"


def test_health_is_never_limited(client):
    for _ in range(10):
        assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/things").status_code == 200  # and health drew nothing from the IP bucket


def test_each_client_ip_has_its_own_bucket(settings, clock):
    app = make_app(settings, clock)
    a = TestClient(app, client=("203.0.113.1", 1))
    b = TestClient(app, client=("203.0.113.2", 1))
    for _ in range(3):
        assert a.get("/api/v1/things").status_code == 200
    assert a.get("/api/v1/things").status_code == 429
    assert b.get("/api/v1/things").status_code == 200


def test_organisation_bucket_is_shared_by_every_address_of_the_organisation(clock):
    # a wide IP limit so the organisation's bucket (5) is the one that empties
    settings = GatewaySettings(ip=Limit(600, 600), organisation=Limit(60, 5), trusted_proxies=())
    app = make_app(settings, clock)
    a = TestClient(app, client=("203.0.113.1", 1))
    b = TestClient(app, client=("203.0.113.2", 1))
    for _ in range(3):
        assert a.get("/api/v1/things", headers=bearer("org-1")).status_code == 200
    for _ in range(2):
        assert b.get("/api/v1/things", headers=bearer("org-1")).status_code == 200
    r = b.get("/api/v1/things", headers=bearer("org-1"))
    assert r.status_code == 429 and r.json()["scope"] == "organisation"
    assert b.get("/api/v1/things", headers=bearer("org-2")).status_code == 200  # another organisation
    assert b.get("/api/v1/things").status_code == 200  # anonymous: IP bucket only


def test_a_bad_or_platform_token_draws_from_the_ip_bucket_only():
    settings = GatewaySettings(ip=Limit(60, 3), organisation=Limit(60, 1), trusted_proxies=())
    limiter = RateLimiter(settings, MemoryStore(), FakeClock())
    assert limiter.organisation("Bearer not-a-token") is None
    assert limiter.organisation(bearer(None)["Authorization"]) is None  # super admin: no organisation
    assert limiter.organisation(bearer("org-9")["Authorization"]) == "org-9"
    assert limiter.organisation(None) is None and limiter.organisation("Basic abc") is None
    for _ in range(3):
        assert limiter.check(path="/api/v1/x", peer="1.1.1.1", forwarded_for=None, authorization="Bearer nope") is None
    denied = limiter.check(path="/api/v1/x", peer="1.1.1.1", forwarded_for=None, authorization="Bearer nope")
    assert denied is not None and denied.scope == "ip"


def test_sign_in_and_sign_up_have_the_stricter_bucket(client, clock):
    assert client.post("/api/v1/identity/auth/login").status_code == 200
    assert client.post("/api/v1/tenancy/register").status_code == 200  # same auth bucket, per address
    r = client.post("/api/v1/identity/auth/login")
    assert r.status_code == 429 and r.json()["scope"] == "auth"
    assert client.get("/api/v1/things").status_code == 200  # the IP bucket (3) still has one
    clock.advance(1.0)
    assert client.post("/api/v1/identity/auth/login").status_code == 200


def test_forwarded_for_counts_only_from_a_trusted_proxy(settings, clock):
    app = make_app(settings, clock)
    proxy = TestClient(app, client=("10.1.2.3", 1))
    stranger = TestClient(app, client=("203.0.113.9", 1))
    # through the proxy: each forwarded client has its own bucket
    for _ in range(3):
        assert proxy.get("/api/v1/things", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 200
    assert proxy.get("/api/v1/things", headers={"X-Forwarded-For": "198.51.100.1"}).status_code == 429
    assert proxy.get("/api/v1/things", headers={"X-Forwarded-For": "198.51.100.2"}).status_code == 200
    # a stranger's header is ignored: every request is the stranger's own bucket
    for i in range(3):
        assert stranger.get("/api/v1/things", headers={"X-Forwarded-For": f"198.51.100.{10 + i}"}).status_code == 200
    assert stranger.get("/api/v1/things", headers={"X-Forwarded-For": "198.51.100.99"}).status_code == 429


def test_client_ip_walks_the_chain_from_the_right_past_trusted_hops():
    limiter = RateLimiter(GatewaySettings(trusted_proxies=("10.0.0.0/8", "::1/128")), MemoryStore())
    assert limiter.client_ip("10.0.0.1", "1.2.3.4, 5.6.7.8, 10.0.0.2") == "5.6.7.8"  # client spoofed 1.2.3.4
    assert limiter.client_ip("10.0.0.1", "5.6.7.8") == "5.6.7.8"
    assert limiter.client_ip("10.0.0.1", "10.0.0.5") == "10.0.0.5"  # every hop trusted: the leftmost
    assert limiter.client_ip("10.0.0.1", None) == "10.0.0.1"
    assert limiter.client_ip("203.0.113.1", "5.6.7.8") == "203.0.113.1"  # not a proxy
    assert limiter.client_ip("testclient", "5.6.7.8") == "testclient"  # not even an address
    assert limiter.client_ip(None, None) == "unknown"
    everyone = RateLimiter(GatewaySettings(trusted_proxies=("*",)), MemoryStore())
    assert everyone.client_ip("203.0.113.1", "5.6.7.8") == "5.6.7.8"


def test_rate_limiting_can_be_switched_off(clock):
    settings = GatewaySettings(rate_limit=False, ip=Limit(60, 1))
    client = TestClient(make_app(settings, clock), client=PEER)
    for _ in range(5):
        assert client.get("/api/v1/things").status_code == 200
