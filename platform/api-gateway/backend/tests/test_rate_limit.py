"""Buckets per client IP, per user and per organisation (bearer token's `sub` and `org`) and the stricter one for
sign-in and sign-up; 429 with Retry-After and a JSON body; health exempt; X-Forwarded-For believed only from a
trusted proxy."""

import asyncio

from conftest import PEER, FakeClock, make_app
from eos_api_gateway import GatewaySettings
from eos_api_gateway.application.limiter import RateLimiter
from eos_api_gateway.domain.bucket import Limit
from eos_api_gateway.infrastructure import MemoryStore
from eos_core.security import create_token
from fastapi.testclient import TestClient


def bearer(org: str | None, user: str = "u1") -> dict[str, str]:
    return {"Authorization": f"Bearer {create_token(user_id=user, organisation_id=org, roles=['student'])}"}


def check(limiter: RateLimiter, **kwargs):
    kwargs.setdefault("claims", None)
    return asyncio.run(limiter.check(**kwargs))


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


def test_a_bad_or_platform_token_draws_from_the_ip_bucket_only(clock):
    settings = GatewaySettings(ip=Limit(60, 3), organisation=Limit(60, 1), trusted_proxies=())
    limiter = RateLimiter(settings, MemoryStore(), FakeClock())
    assert limiter.principal(None) == (None, None)
    assert limiter.principal({"sub": "root", "org": None}) == (None, "root")  # super admin: no organisation
    assert limiter.principal({"sub": "u9", "org": "org-9"}) == ("org-9", "u9")
    for _ in range(3):
        assert check(limiter, path="/api/v1/x", peer="1.1.1.1", forwarded_for=None) is None
    denied = check(limiter, path="/api/v1/x", peer="1.1.1.1", forwarded_for=None)
    assert denied is not None and denied.scope == "ip"
    # through the middleware: a forged token and a platform token are the address's, like no token
    client = TestClient(make_app(settings, clock), client=("198.51.100.30", 1))
    assert client.get("/api/v1/things", headers={"Authorization": "Bearer not-a-token"}).status_code == 200
    assert client.get("/api/v1/things", headers=bearer(None)).status_code == 200
    assert client.get("/api/v1/things", headers={"Authorization": "Basic abc"}).status_code == 200
    assert client.get("/api/v1/things", headers=bearer(None)).json()["scope"] == "ip"


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


WRONG = {"email": "Head@School.example.com", "password": "wrong"}
RIGHT = {**WRONG, "password": "right"}


def test_ten_failed_attempts_at_one_account_from_one_address_stop_that_pair(clock):
    app = make_app(GatewaySettings(trusted_proxies=()), clock)
    attacker = TestClient(app, client=("198.51.100.1", 1))
    for _ in range(10):
        assert attacker.post("/api/v1/identity/auth/login", json=WRONG).status_code == 401
    r = attacker.post("/api/v1/identity/auth/login", json={**WRONG, "email": "head@school.example.com"})
    assert r.status_code == 429 and r.json()["scope"] == "login"
    assert r.json()["detail"].startswith("too many requests for sign-in to this account from this address")
    assert r.headers["retry-after"] == "6"  # 10 a minute: one every 6 s
    # even the right password is held back for that pair, until a token has refilled
    assert attacker.post("/api/v1/identity/auth/login", json=RIGHT).status_code == 429
    # another account from the same address is not affected
    assert attacker.post("/api/v1/identity/auth/login", json={"email": "pupil@school.example.com"}).status_code == 200
    clock.advance(6.0)
    assert attacker.post("/api/v1/identity/auth/login", json=RIGHT).status_code == 200


def test_an_attacker_cannot_lock_the_account_out_for_its_owner_at_another_address(clock):
    app = make_app(GatewaySettings(trusted_proxies=()), clock)
    attacker = TestClient(app, client=("198.51.100.1", 1))
    owner = TestClient(app, client=("203.0.113.77", 1))
    for _ in range(10):
        assert attacker.post("/api/v1/identity/auth/login", json=WRONG).status_code == 401
    assert attacker.post("/api/v1/identity/auth/login", json=WRONG).status_code == 429  # the pair is shut
    for _ in range(10):  # the owner, from elsewhere, signs in as often as they like
        assert owner.post("/api/v1/identity/auth/login", json=RIGHT).status_code == 200
    # and the attacker's refused attempts keep the pair shut without ever touching the owner's pair
    for _ in range(5):
        assert attacker.post("/api/v1/identity/auth/login", json=WRONG).status_code == 429
        assert owner.post("/api/v1/identity/auth/login", json=RIGHT).status_code == 200


def test_successful_sign_ins_do_not_use_up_attempts(clock):
    app = make_app(GatewaySettings(trusted_proxies=()), clock)
    campus = TestClient(app, client=("198.51.100.1", 1))
    for _ in range(30):  # three times the bucket, the same account from the same address
        assert campus.post("/api/v1/identity/auth/login", json=RIGHT).status_code == 200
    # and the nine failures that still fit before the tenth are all that this pair has used
    for _ in range(10):
        assert campus.post("/api/v1/identity/auth/login", json=WRONG).status_code == 401
    assert campus.post("/api/v1/identity/auth/login", json=WRONG).status_code == 429


def test_only_a_refused_sign_in_counts_not_a_malformed_one(clock):
    app = make_app(GatewaySettings(trusted_proxies=()), clock)
    client = TestClient(app, client=("198.51.100.1", 1))
    for _ in range(15):
        assert client.post("/api/v1/identity/auth/login", json={**WRONG, "password": "malformed"}).status_code == 422
    for _ in range(10):
        assert client.post("/api/v1/identity/auth/login", json=WRONG).status_code == 401
    assert client.post("/api/v1/identity/auth/login", json=WRONG).status_code == 429


def test_a_success_in_the_middle_does_not_refill_what_failures_took(clock):
    app = make_app(GatewaySettings(trusted_proxies=()), clock)
    client = TestClient(app, client=("198.51.100.1", 1))
    for _ in range(9):
        assert client.post("/api/v1/identity/auth/login", json=WRONG).status_code == 401
    for _ in range(5):
        assert client.post("/api/v1/identity/auth/login", json=RIGHT).status_code == 200
    assert client.post("/api/v1/identity/auth/login", json=WRONG).status_code == 401  # the tenth
    assert client.post("/api/v1/identity/auth/login", json=WRONG).status_code == 429


def test_a_login_body_that_cannot_be_read_still_meets_the_address_bucket(settings, clock):
    client = TestClient(make_app(settings, clock), client=PEER)
    assert client.post("/api/v1/identity/auth/login", content=b"not json").status_code == 200
    assert client.post("/api/v1/identity/auth/login", json=["a list"]).status_code == 200
    r = client.post("/api/v1/identity/auth/login", json={"email": 5})
    assert r.status_code == 429 and r.json()["scope"] == "auth"  # the auth bucket (2) is empty


def test_the_account_key_is_a_digest_not_the_address(clock):
    store = MemoryStore()
    limiter = RateLimiter(GatewaySettings(trusted_proxies=()), store, clock)
    check(
        limiter,
        path="/api/v1/identity/auth/login",
        peer="1.1.1.1",
        forwarded_for=None,
        login_email="Head@School.example.com",
    )
    keys = list(store._buckets)
    assert not any("school" in k.lower() for k in keys), keys
    assert sum(k.startswith("login:") for k in keys) == 1
    assert all(k.endswith(":1.1.1.1") for k in keys if k.startswith("login:"))  # the account at that address


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
        async def run(keys, args):
            self.calls += 1
            raise ConnectionError("redis down")

        return run


def test_an_unreachable_redis_fails_open_and_is_left_alone_for_thirty_seconds():
    from eos_api_gateway.infrastructure.redis_store import RETRY_AFTER_FAILURE, RedisStore

    client, clock = _DownRedis(), FakeClock()
    store = RedisStore(client, clock=clock)
    limit = Limit(60, 1)
    for _ in range(50):
        assert asyncio.run(store.take("ip:x", limit, 0.0)) is None  # allowed
    assert client.calls == 1  # asked once, then skipped
    clock.advance(RETRY_AFTER_FAILURE)
    assert asyncio.run(store.take("ip:x", limit, 0.0)) is None
    assert client.calls == 2
    asyncio.run(store.refund("ip:x", limit, 0.0))  # down again: skipped, no error
    assert client.calls == 2


def test_the_redis_client_is_asyncio_with_short_timeouts_and_no_retries():
    import redis.asyncio
    from eos_api_gateway.infrastructure.redis_store import CONNECT_TIMEOUT, RedisStore

    store = RedisStore.from_url("redis://127.0.0.1:1/0")  # nothing listens there
    assert isinstance(store._client, redis.asyncio.Redis)  # awaited: a slow Redis never holds the event loop
    kwargs = store._client.connection_pool.connection_kwargs
    assert kwargs["socket_connect_timeout"] == CONNECT_TIMEOUT <= 0.1 and kwargs["socket_timeout"] <= 0.25
    assert asyncio.run(store.take("ip:y", Limit(60, 1), 0.0)) is None  # connection refused: allowed


# Review of PR 363 (Srujan): the body read for the per-account bucket is bounded, chunked or not.

PREFIX = b'{"email": "head@school.example.com", "password": "guess", "pad": "'


def _chunks(total: int):
    """A JSON sign-in body of `total` bytes of padding, sent chunked (no Content-Length)."""
    yield PREFIX
    for _ in range(total // 1024):
        yield b"x" * 1024
    yield b'"}'


def _chunked_app(clock, store):
    from eos_api_gateway import RateLimit
    from fastapi import FastAPI, Request

    app = FastAPI()
    received: list[int] = []

    @app.post("/api/v1/identity/auth/login")
    async def login(request: Request):
        received.append(len(await request.body()))
        return {}

    app.add_middleware(RateLimit, settings=GatewaySettings(trusted_proxies=()), store=store, clock=clock)
    return app, received


def test_a_small_chunked_login_body_is_keyed_on_its_email(clock):
    store = MemoryStore()
    app, received = _chunked_app(clock, store)
    r = TestClient(app, client=PEER).post("/api/v1/identity/auth/login", content=_chunks(2048))
    assert r.status_code == 200
    assert sum(k.startswith("login:") for k in store._buckets) == 1
    assert received == [len(PREFIX) + 2048 + 2]


def test_a_chunked_login_body_past_16_kib_is_refused_with_413_and_never_reaches_the_route(clock):
    """Second review of PR 363: padding the body past the limit used to skip the per-account bucket (the email
    was never read) while the route still parsed it. A real sign-in is never near 16 KiB: refuse it."""
    store = MemoryStore()
    app, received = _chunked_app(clock, store)
    r = TestClient(app, client=PEER).post("/api/v1/identity/auth/login", content=_chunks(200 * 1024))
    assert r.status_code == 413
    assert r.json() == {"detail": "the request body is larger than 16384 bytes", "code": "body_too_large"}
    assert received == [] and len(store) == 0  # the route never ran, no bucket was charged


def test_a_padded_login_body_with_a_content_length_is_refused_before_it_is_read(clock):
    app = make_app(GatewaySettings(trusted_proxies=()), clock)
    client = TestClient(app, client=PEER)
    padded = {**WRONG, "pad": " " * (16 * 1024)}
    for _ in range(12):  # past the per-account bucket (10): every one is 413, never a guess
        assert client.post("/api/v1/identity/auth/login", json=padded).status_code == 413
    assert client.post("/api/v1/tenancy/register", json={"pad": "x" * 20_000}).status_code == 413  # sign-up too
    assert client.post("/api/v1/identity/auth/login", json=WRONG).status_code == 401  # a normal one is answered


def test_the_login_body_reader_stops_at_the_limit(clock):
    import pytest
    from eos_api_gateway.api.middleware import _AUTH_BODY_LIMIT, BodyTooLargeError, _read_bounded_body
    from starlette.requests import Request

    sent = 0

    async def receive():
        nonlocal sent
        sent += 1024
        return {"type": "http.request", "body": b"x" * 1024, "more_body": True}  # never ends

    scope = {"type": "http", "method": "POST", "headers": [], "path": "/api/v1/identity/auth/login"}
    with pytest.raises(BodyTooLargeError):
        asyncio.run(_read_bounded_body(Request(scope, receive)))
    assert _AUTH_BODY_LIMIT < sent <= _AUTH_BODY_LIMIT + 1024  # one chunk past the limit, then it stopped


# Second review of PR 363, point 2: one user cannot rate-limit the whole organisation.


def test_one_user_hammering_gets_429_while_another_user_of_the_organisation_is_fine(clock):
    settings = GatewaySettings(user=Limit(60, 3), organisation=Limit(60, 100), trusted_proxies=())
    app = make_app(settings, clock)
    script = TestClient(app, client=("203.0.113.50", 1))
    teacher = TestClient(app, client=("203.0.113.50", 2))  # same campus, same address
    for _ in range(3):
        assert script.get("/api/v1/things", headers=bearer("org-1", "student-7")).status_code == 200
    for _ in range(20):
        r = script.get("/api/v1/things", headers=bearer("org-1", "student-7"))
        assert r.status_code == 429 and r.json()["scope"] == "user"
    assert r.json()["detail"].startswith("too many requests for your account")
    for _ in range(3):
        assert teacher.get("/api/v1/things", headers=bearer("org-1", "teacher-1")).status_code == 200
    clock.advance(1.0)  # one token a second for the script again
    assert script.get("/api/v1/things", headers=bearer("org-1", "student-7")).status_code == 200


def test_the_organisation_bucket_stays_the_ceiling_and_a_refusal_charges_nothing(clock):
    settings = GatewaySettings(user=Limit(60, 2), organisation=Limit(60, 4), trusted_proxies=())
    store = MemoryStore()
    client = TestClient(make_app(settings, clock, store), client=PEER)
    for _ in range(2):
        assert client.get("/api/v1/things", headers=bearer("org-1", "a")).status_code == 200
    for _ in range(10):  # refused by a's own bucket: the organisation's is not touched
        assert client.get("/api/v1/things", headers=bearer("org-1", "a")).json()["scope"] == "user"
    for _ in range(2):
        assert client.get("/api/v1/things", headers=bearer("org-1", "b")).status_code == 200
    r = client.get("/api/v1/things", headers=bearer("org-1", "c"))  # four served: the organisation is full
    assert r.status_code == 429 and r.json()["scope"] == "organisation"
    assert store._buckets["user:org-1:c"][0].tokens == 2  # c's own token was given back
    assert client.get("/api/v1/things", headers=bearer("org-2", "c")).status_code == 200  # another organisation


def test_the_default_limits_carry_a_results_day_of_500_users():
    """README (Sizing the limits): 500 users of one organisation each loading a dashboard of 24 widgets within a
    minute is 12 000 requests, the organisation's default; one user is held to 300 a minute."""
    settings = GatewaySettings(trusted_proxies=())
    limiter = RateLimiter(settings, MemoryStore(), FakeClock())

    async def day():
        refused = 0
        for user in range(500):
            for _ in range(24):
                refused += (
                    await limiter.check(
                        path="/api/v1/x",
                        peer="203.0.113.60",
                        forwarded_for=None,
                        claims={"org": "o", "sub": f"u{user}"},
                    )
                    is not None
                )
        late = await limiter.check(
            path="/api/v1/x", peer="203.0.113.60", forwarded_for=None, claims={"org": "o", "sub": "u-late"}
        )
        return refused, late

    refused, late = asyncio.run(day())
    assert refused == 0 and late is not None and late.scope == "organisation"
    assert settings.user == Limit(300, 300) and settings.organisation == Limit(12000, 12000)
    one = RateLimiter(settings, MemoryStore(), FakeClock())
    results = [
        check(one, path="/api/v1/x", peer="203.0.113.61", forwarded_for=None, claims={"org": "o", "sub": "s"})
        for _ in range(301)
    ]
    assert results[:300] == [None] * 300 and results[300].scope == "user"


# Second review of PR 363, point 6: the OIDC sign-in is an auth path.


def test_the_oidc_sign_in_draws_from_the_auth_bucket(settings, clock):
    limiter = RateLimiter(GatewaySettings(), MemoryStore(), clock)
    assert limiter.is_auth_path("/api/v1/identity/auth/oidc/callback")
    assert limiter.is_auth_path("/api/v1/identity/auth/oidc/config")
    app = make_app(settings, clock)

    @app.post("/api/v1/identity/auth/oidc/callback")
    def callback():
        return {"token": "x"}

    client = TestClient(app, client=PEER)
    assert client.post("/api/v1/identity/auth/oidc/callback", json={"code": "c"}).status_code == 200
    assert client.post("/api/v1/identity/auth/login").status_code == 200
    r = client.post("/api/v1/identity/auth/oidc/callback", json={"code": "c"})
    assert r.status_code == 429 and r.json()["scope"] == "auth"  # auth bucket (2) shared with sign-in


# Second review of PR 363, nit: a sign-in the address bucket refuses is given back to the auth and login buckets.


def test_a_sign_in_refused_by_the_address_bucket_is_refunded_to_the_auth_and_login_buckets(clock):
    settings = GatewaySettings(ip=Limit(60, 1), auth=Limit(60, 5), login=Limit(60, 10), trusted_proxies=())
    store = MemoryStore()
    client = TestClient(make_app(settings, clock, store), client=PEER)
    assert client.get("/api/v1/things").status_code == 200  # the address bucket (1) is now empty
    for _ in range(8):
        r = client.post("/api/v1/identity/auth/login", json=WRONG)
        assert r.status_code == 429 and r.json()["scope"] == "ip"
    (auth_key,) = [k for k in store._buckets if k.startswith("auth:")]
    (login_key,) = [k for k in store._buckets if k.startswith("login:")]
    assert store._buckets[auth_key][0].tokens == 5 and store._buckets[login_key][0].tokens == 10  # all given back


# Second review of PR 363, point 9: IPv6 clients are keyed by their /64.


def test_ipv6_clients_are_keyed_by_their_slash_64():
    limiter = RateLimiter(GatewaySettings(trusted_proxies=("10.0.0.0/8",)), MemoryStore())
    assert limiter.client_key("2001:db8:1:2:aaaa::1", None) == "2001:db8:1:2::/64"
    assert limiter.client_key("2001:db8:1:2:ffff:ffff:ffff:ffff", None) == "2001:db8:1:2::/64"
    assert limiter.client_key("2001:db8:1:3::1", None) == "2001:db8:1:3::/64"
    assert limiter.client_key("::ffff:203.0.113.9", None) == "203.0.113.9"  # IPv4-mapped: the IPv4 address
    assert limiter.client_key("203.0.113.9", None) == "203.0.113.9"
    assert limiter.client_key("10.0.0.1", "2001:db8:9:9::42") == "2001:db8:9:9::/64"  # forwarded, too
    assert limiter.client_key("testclient", None) == "testclient"


def test_rotating_addresses_inside_one_ipv6_slash_64_shares_one_bucket(settings, clock):
    app = make_app(settings, clock)  # IP bucket: 3; auth bucket: 2
    for i in range(3):
        rotating = TestClient(app, client=(f"2001:db8:1:2::{i + 1:x}", 1))
        assert rotating.get("/api/v1/things").status_code == 200
    r = TestClient(app, client=("2001:db8:1:2:dead:beef:0:1", 1)).get("/api/v1/things")
    assert r.status_code == 429 and r.json()["scope"] == "ip"
    assert TestClient(app, client=("2001:db8:1:3::1", 1)).get("/api/v1/things").status_code == 200  # next /64
    for i in range(2):  # the sign-up bucket of another /64 (2), its address bucket (3) still has room
        assert TestClient(app, client=(f"2001:db8:1:4::a{i}", 1)).post("/api/v1/tenancy/register").status_code == 200
    r = TestClient(app, client=("2001:db8:1:4::b0", 1)).post("/api/v1/tenancy/register")
    assert r.status_code == 429 and r.json()["scope"] == "auth"


# Second review of PR 363, point 8: the bearer token is decoded once per request, a realm token off the loop.


def test_the_token_is_decoded_once_per_request_and_shared_through_request_state(settings, clock, monkeypatch):
    import jwt
    from eos_api_gateway import token_claims
    from eos_api_gateway.api import claims as claims_module
    from fastapi import Request

    calls = []
    real = claims_module.decode

    async def counted(token):
        calls.append(token)
        return await real(token)

    monkeypatch.setattr(claims_module, "decode", counted)
    app = make_app(settings, clock)

    @app.get("/api/v1/whoami")
    async def whoami(request: Request):
        first = await token_claims(request)  # what the entitlement gate and the routes ask
        assert await token_claims(request) is first
        assert request.state.token_claims is first
        return {"sub": first["sub"] if first else None}

    @app.get("/api/v1/invalid")
    async def invalid(request: Request):
        try:
            await token_claims(request)
        except jwt.PyJWTError as e:
            return {"error": type(e).__name__, "same": e is request.state.token_error}
        return {}

    client = TestClient(app, client=PEER)
    assert client.get("/api/v1/whoami", headers=bearer("org-1", "u5")).json() == {"sub": "u5"}
    assert len(calls) == 1  # the limiter decoded it; the route reused it
    assert client.get("/api/v1/invalid", headers={"Authorization": "Bearer forged"}).json() == {
        "error": "DecodeError",
        "same": True,
    }
    assert len(calls) == 2  # once for the forged token, too
    assert client.get("/api/v1/whoami").json() == {"sub": None} and len(calls) == 2  # no token, nothing decoded


def test_a_realm_token_is_decoded_in_the_thread_pool(monkeypatch):
    import base64
    import json
    import threading

    from eos_api_gateway.api import claims as claims_module

    threads = []

    def fake_decode(token):
        threads.append(threading.get_ident())
        return {"sub": "kc-user", "org": "org-1"}

    monkeypatch.setattr(claims_module, "decode_token", fake_decode)

    def segment(data: dict) -> str:
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()

    realm_token = f"{segment({'alg': 'RS256', 'kid': 'k'})}.{segment({'sub': 'x'})}.c2ln"
    own_token = f"{segment({'alg': 'HS256'})}.{segment({'sub': 'x'})}.c2ln"

    async def both():
        loop_thread = threading.get_ident()
        await claims_module.decode(realm_token)
        await claims_module.decode(own_token)
        return loop_thread

    loop_thread = asyncio.run(both())
    assert threads[0] != loop_thread  # RS256: JWKS fetch and the resolver's query run in the pool
    assert threads[1] == loop_thread  # HS256: one HMAC, decoded in place
