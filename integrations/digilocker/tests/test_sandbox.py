"""Contract tests against DigiLocker's sandbox. Skipped unless the sandbox is configured:

    DIGILOCKER_SANDBOX_BASE_URL, DIGILOCKER_SANDBOX_REQUESTER_CLIENT_ID, DIGILOCKER_SANDBOX_REQUESTER_CLIENT_SECRET
    DIGILOCKER_SANDBOX_TEST_ISSUER_ID, DIGILOCKER_SANDBOX_TEST_ISSUER_API_KEY

These make real calls, so they run by hand, never in CI (no secrets there). conftest clears DIGILOCKER_* for every
test, so the values are read from the process environment before that."""

import os

import pytest
from dgl_support import Org, ctx, ok

SANDBOX = {k: os.environ.get(k, "") for k in (
    "DIGILOCKER_SANDBOX_BASE_URL", "DIGILOCKER_SANDBOX_REQUESTER_CLIENT_ID", "DIGILOCKER_SANDBOX_REQUESTER_CLIENT_SECRET",
    "DIGILOCKER_SANDBOX_TEST_ISSUER_ID", "DIGILOCKER_SANDBOX_TEST_ISSUER_API_KEY")}  # fmt: skip

pytestmark = pytest.mark.skipif(not all(SANDBOX.values()), reason="DigiLocker sandbox is not configured")


def test_authorize_url_against_the_sandbox_app(adapter, monkeypatch):
    for k in (
        "DIGILOCKER_SANDBOX_BASE_URL",
        "DIGILOCKER_SANDBOX_REQUESTER_CLIENT_ID",
        "DIGILOCKER_SANDBOX_REQUESTER_CLIENT_SECRET",
    ):
        monkeypatch.setenv(k, SANDBOX[k])
    adapter.runtime.http_factory = lambda: __import__("httpx").Client()
    inp = {"state": "state-abcdef", "code_challenge": "a" * 43, "redirect_uri": "https://eos.example.com/cb"}
    url = ok(adapter.invoke("begin_authorisation", ctx(Org(), mode="sandbox"), inp))["authorize_url"]
    assert url.startswith(SANDBOX["DIGILOCKER_SANDBOX_BASE_URL"])
