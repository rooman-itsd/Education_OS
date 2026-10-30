"""Every response carries the security headers; HSTS only when the request came in over HTTPS."""

from conftest import PEER, make_app
from eos_api_gateway import GatewaySettings
from eos_api_gateway.api.middleware import CSP
from fastapi.testclient import TestClient

EXPECTED = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
    "content-security-policy": CSP,
}


def test_api_responses_carry_the_headers_and_no_store(client):
    r = client.get("/api/v1/things")
    assert r.status_code == 200
    for header, value in EXPECTED.items():
        assert r.headers[header] == value, header
    assert "camera=()" in r.headers["permissions-policy"]
    assert r.headers["cache-control"] == "no-store"
    assert "strict-transport-security" not in r.headers  # plain http


def test_hsts_only_over_https_direct_or_through_the_proxy(settings):
    app = make_app(settings)
    r = TestClient(app, client=PEER).get("/api/v1/things", headers={"X-Forwarded-Proto": "https"})
    assert r.headers["strict-transport-security"] == "max-age=31536000; includeSubDomains"
    r = TestClient(app, base_url="https://testserver", client=PEER).get("/api/v1/things")
    assert r.headers["strict-transport-security"].startswith("max-age=")
    r = TestClient(app, client=PEER).get("/api/v1/things", headers={"X-Forwarded-Proto": "http"})
    assert "strict-transport-security" not in r.headers


def test_a_route_that_sets_its_own_cache_control_keeps_it(client):
    assert client.get("/api/v1/cached").headers["cache-control"] == "private, max-age=60"


def test_the_docs_pages_keep_every_header_but_the_csp(client):
    r = client.get("/docs")
    assert r.headers["x-frame-options"] == "DENY"
    assert "content-security-policy" not in r.headers
    assert "cache-control" not in r.headers  # not under /api/


def test_refusals_carry_the_headers_too(client):
    for _ in range(3):
        client.get("/api/v1/things")
    r = client.get("/api/v1/things")
    assert r.status_code == 429 and r.headers["x-content-type-options"] == "nosniff"


def test_headers_can_be_switched_off_for_local_dev_only():
    settings = GatewaySettings(security_headers=False, rate_limit=False)
    r = TestClient(make_app(settings), client=PEER).get("/api/v1/things")
    assert "x-frame-options" not in r.headers and "content-security-policy" not in r.headers
