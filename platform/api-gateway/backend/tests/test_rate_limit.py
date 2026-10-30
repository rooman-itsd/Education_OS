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
    assert limiter.client_ip("10.0.0.1", "10.0.0.5") == "10.0.0.5"  # every hop trusted: the rightmost
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


# Review of PR 363, point 1: a campus behind one NAT address.


def test_signed_in_requests_are_charged_to_the_organisation_only(clock):
    """A campus is one NAT address: its signed-in users must not use up the address's bucket."""
    settings = GatewaySettings(ip=Limit(60, 2), organisation=Limit(60, 50), trusted_proxies=())
    campus = TestClient(make_app(settings, clock), client=("203.0.113.40", 1))
    for _ in range(30):  # far past the IP bucket (2), all signed in
        assert campus.get("/api/v1/things", headers=bearer("org-1")).status_code == 200
    # the address's bucket is untouched: anonymous requests from the same campus still pass
    assert campus.get("/api/v1/things").status_code == 200
    assert campus.get("/api/v1/things").status_code == 200
    r = campus.get("/api/v1/things")
    assert r.status_code == 429 and r.json()["scope"] == "ip"
    # an invalid token is anonymous: the (now empty) IP bucket refuses it
    assert campus.get("/api/v1/things", headers={"Authorization": "Bearer forged"}).json()["scope"] == "ip"
    # and the organisation still has its own bucket
    assert campus.get("/api/v1/things", headers=bearer("org-1")).status_code == 200


def test_a_lab_of_forty_signs_in_together_under_the_default_limits(clock):
    settings = GatewaySettings(trusted_proxies=())  # the defaults: auth 60 a minute per address
    campus = TestClient(make_app(settings, clock), client=("203.0.113.41", 1))
    for i in range(40):
        r = campus.post("/api/v1/identity/auth/login", json={"email": f"pupil{i}@school.example.com"})
        assert r.status_code == 200, (i, r.text)


def test_one_account_gets_ten_guesses_a_minute_whatever_the_address(clock):
    settings = GatewaySettings(trusted_proxies=())
    app = make_app(settings, clock)
    body = {"email": "Head@School.example.com", "password": "guess"}
    for i in range(10):
        address = TestClient(app, client=(f"198.51.100.{i + 1}", 1))
        assert address.post("/api/v1/identity/auth/login", json=body).status_code == 200
    other = TestClient(app, client=("198.51.100.99", 1))
    r = other.post("/api/v1/identity/auth/login", json={**body, "email": "head@school.example.com"})
    assert r.status_code == 429 and r.json()["scope"] == "login"
    assert r.json()["detail"].startswith("too many requests for sign-in to this account")
    assert r.headers["retry-after"] == "6"  # 10 a minute: one every 6 s
    # another account from the same address is not affected
    assert other.post("/api/v1/identity/auth/login", json={"email": "pupil@school.example.com"}).status_code == 200
    clock.advance(6.0)
    assert other.post("/api/v1/identity/auth/login", json=body).status_code == 200


def test_a_login_body_that_cannot_be_read_still_meets_the_address_bucket(settings, clock):
    client = TestClient(make_app(settings, clock), client=PEER)
    assert client.post("/api/v1/identity/auth/login", content=b"not json").status_code == 200
    assert client.post("/api/v1/identity/auth/login", json=["a list"]).status_code == 200
    r = client.post("/api/v1/identity/auth/login", json={"email": 5})
    assert r.status_code == 429 and r.json()["scope"] == "auth"  # the auth bucket (2) is empty


def test_the_account_key_is_a_digest_not_the_address(clock):
    store = MemoryStore()
    limiter = RateLimiter(GatewaySettings(trusted_proxies=()), store, clock)
    limiter.check(
        path="/api/v1/identity/auth/login",
        peer="1.1.1.1",
        forwarded_for=None,
        authorization=None,
        login_email="Head@School.example.com",
    )
    keys = list(store._buckets)
    assert not any("school" in k.lower() for k in keys), keys
    assert sum(k.startswith("login:") for k in keys) == 1


def test_public_module_routes_share_the_auth_bucket(settings, clock):
    limiter = RateLimiter(settings, MemoryStore(), clock)
    assert limiter.is_auth_path("/api/v1/admissions/public/st-marys/applications")
    assert limiter.is_auth_path("/api/v1/web-portal-cms/public/st-marys/pages/home")
    assert not limiter.is_auth_path("/api/v1/admissions/applications")
    assert not limiter.is_auth_path("/api/v1/admissions/public")  # not a route under public/
    app = make_app(settings, clock)

    @app.post("/api/v1/admissions/public/{slug}/applications")
    def apply(slug: str):
        return {"slug": slug}

    client = TestClient(app, client=PEER)
    assert client.post("/api/v1/admissions/public/a/applications").status_code == 200
    assert client.post("/api/v1/identity/auth/login").status_code == 200
    r = client.post("/api/v1/admissions/public/a/applications")
    assert r.status_code == 429 and r.json()["scope"] == "auth"  # auth bucket (2) shared with sign-in


# Review of PR 363, point 2: X-Forwarded-For from untrusted peers.


def test_by_default_only_loopback_is_a_proxy_so_a_lan_client_cannot_forge_its_address(clock):
    settings = GatewaySettings(ip=Limit(60, 2))  # default trusted proxies: loopback only
    lan_client = TestClient(make_app(settings, clock), client=("192.168.1.77", 1))
    for i in range(2):
        assert lan_client.get("/api/v1/things", headers={"X-Forwarded-For": f"10.9.9.{i}"}).status_code == 200
    r = lan_client.get("/api/v1/things", headers={"X-Forwarded-For": "10.9.9.200"})
    assert r.status_code == 429  # every forged address landed in the LAN client's own bucket


def test_a_chain_through_trusted_proxies_resolves_to_the_hop_the_proxy_saw():
    limiter = RateLimiter(GatewaySettings(trusted_proxies=("192.0.2.10", "127.0.0.1")), MemoryStore())
    # client 198.51.100.4 forged "1.2.3.4"; nginx (192.0.2.10) appended it; a local hop (127.0.0.1) forwarded
    assert limiter.client_ip("127.0.0.1", "1.2.3.4, 198.51.100.4, 192.0.2.10") == "198.51.100.4"
    # a LAN address is a client like any other unless it is configured as a proxy
    assert limiter.client_ip("192.0.2.10", "5.5.5.5, 192.168.1.77") == "192.168.1.77"
    # every hop a proxy: the rightmost, which a proxy wrote, never the client-written leftmost
    assert limiter.client_ip("192.0.2.10", "8.8.8.8, 127.0.0.1, 192.0.2.10") == "8.8.8.8"
    assert limiter.client_ip("192.0.2.10", "127.0.0.1, 192.0.2.10") == "192.0.2.10"
    everyone = RateLimiter(GatewaySettings(trusted_proxies=("*",)), MemoryStore())
    assert everyone.client_ip("203.0.113.1", "1.2.3.4, 5.6.7.8") == "5.6.7.8"  # one hop: what the peer saw


# Review notes: a Redis outage fails open and fast.


class _DownRedis:
    def __init__(self) -> None:
        self.calls = 0

    def register_script(self, _source):
        def run(keys, args):
            self.calls += 1
            raise ConnectionError("redis down")

        return run


def test_an_unreachable_redis_fails_open_and_is_left_alone_for_thirty_seconds():
    from eos_api_gateway.infrastructure.redis_store import RETRY_AFTER_FAILURE, RedisStore

    client, clock = _DownRedis(), FakeClock()
    store = RedisStore(client, clock=clock)
    limit = Limit(60, 1)
    for _ in range(50):
        assert store.take("ip:x", limit, 0.0) is None  # allowed
    assert client.calls == 1  # asked once, then skipped
    clock.advance(RETRY_AFTER_FAILURE)
    assert store.take("ip:x", limit, 0.0) is None
    assert client.calls == 2


def test_the_redis_client_has_short_timeouts_and_no_retries():
    from eos_api_gateway.infrastructure.redis_store import CONNECT_TIMEOUT, RedisStore

    store = RedisStore.from_url("redis://127.0.0.1:1/0")  # nothing listens there
    kwargs = store._client.connection_pool.connection_kwargs
    assert kwargs["socket_connect_timeout"] == CONNECT_TIMEOUT <= 0.1 and kwargs["socket_timeout"] <= 0.25
    assert store.take("ip:y", Limit(60, 1), 0.0) is None  # connection refused: allowed
