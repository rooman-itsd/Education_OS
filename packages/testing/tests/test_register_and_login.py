"""register_and_login reads the verification token from the register response (dev mode) and nowhere else.

Since #361 tenancy sends the verification mail through platform/notification, not the eos_core.notify stub, and this
package may not import platform services. Without the token the helper must say so plainly, not fail with
StopIteration while searching a stub that no longer receives the mail."""

from __future__ import annotations

import pytest
from eos_core import notify
from eos_testing import register_and_login


class _Response:
    def __init__(self, status_code: int, body: dict) -> None:
        self.status_code = status_code
        self._body = body
        self.text = str(body)

    def json(self) -> dict:
        return self._body


class _Client:
    """Answers the three calls register_and_login makes; `token` is what the register response carries."""

    def __init__(self, token: str | None) -> None:
        self.token = token
        self.calls: list[tuple[str, dict]] = []

    def post(self, path: str, json: dict, headers: dict | None = None) -> _Response:
        self.calls.append((path, json))
        if path == "/api/v1/tenancy/register":
            body = {"id": "org-1", "slug": json["slug"]}
            if self.token:
                body["verification_token"] = self.token
            return _Response(201, body)
        if path == "/api/v1/tenancy/register/verify":
            assert json == {"token": self.token}
            return _Response(200, {"status": "active"})
        if path == "/api/v1/identity/auth/login":
            return _Response(200, {"token": "session-token"})
        raise AssertionError(f"unexpected call {path}")


def test_the_dev_mode_token_verifies_and_signs_in():
    client = _Client(token="verify-me")
    result = register_and_login(client, slug="alpha")
    assert result["token"] == "session-token" and result["email"] == "admin@alpha.example.com"
    assert [path for path, _ in client.calls] == [
        "/api/v1/tenancy/register",
        "/api/v1/tenancy/register/verify",
        "/api/v1/identity/auth/login",
    ]


def test_without_the_token_it_says_dev_mode_is_needed():
    client = _Client(token=None)
    with pytest.raises(AssertionError, match="EOS_DEV_MODE=true"):
        register_and_login(client, slug="beta")
    assert [path for path, _ in client.calls] == ["/api/v1/tenancy/register"]  # never verifies with a guessed token


def test_the_legacy_stub_is_never_read_for_the_token():
    """A mail in eos_core.notify.sent (where verification mails used to go) is not used as the token."""
    notify.send_email("admin@gamma.example.com", "Verify your email", "body", token="stale-stub-token")
    client = _Client(token=None)
    with pytest.raises(AssertionError, match="EOS_DEV_MODE=true"):
        register_and_login(client, slug="gamma")
