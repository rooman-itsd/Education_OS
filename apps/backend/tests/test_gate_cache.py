"""EOS_GATE_CACHE_SECONDS: the entitlement gate may reuse its database answers for a few seconds.

The gate's lookups (the organisation's entitlement and the user's status on feature modules, the organisation's status
on platform services) were the largest single cost in the 20 Nov profile (tests/performance/README.md). With the
setting at 0, the default, nothing is reused and a suspension takes effect on the next request, as before. With N > 0,
an answer is reused for N seconds, per API process, so a change takes effect within N seconds."""

import pytest
from eos_backend import gateway
from eos_testing import register_and_login
from eos_testing.tenancy import auth

SA = {"email": "root@platform.example.com", "password": "RootPassw0rd!"}


@pytest.fixture(autouse=True)
def fresh_cache(monkeypatch):
    gateway.clear_cache()
    yield
    gateway.clear_cache()


def _counting(monkeypatch, name: str) -> list[int]:
    calls = [0]
    original = getattr(gateway, name)

    def counted(*args):
        calls[0] += 1
        return original(*args)

    monkeypatch.setattr(gateway, name, counted)
    return calls


def _suspend(client, org_id: str, status: str) -> None:
    sa = auth(client.post("/api/v1/identity/auth/login", json=SA).json()["token"])
    r = client.put(
        f"/api/v1/tenancy/admin/organisations/{org_id}/status", json={"status": status, "reason": "cache"}, headers=sa
    )
    assert r.status_code == 200, r.text


def _later(monkeypatch, seconds: float) -> None:
    now = gateway.time.monotonic()
    monkeypatch.setattr(gateway.time, "monotonic", lambda: now + seconds)


@pytest.mark.parametrize("value", [None, "0", "", "-5", "not a number"])
def test_by_default_nothing_is_reused_and_a_suspension_applies_on_the_next_request(client, monkeypatch, value):
    if value is None:
        monkeypatch.delenv(gateway.CACHE_SETTING, raising=False)
    else:
        monkeypatch.setenv(gateway.CACHE_SETTING, value)
    assert gateway.cache_seconds() == 0
    a = register_and_login(client, slug=f"gc-off-{abs(hash(value)) % 10_000}", academy_type="dance-academy")
    h = auth(a["token"])
    lookups = _counting(monkeypatch, "_entitlement")
    for _ in range(3):
        assert client.get("/api/v1/lms/ping", headers=h).status_code == 200
    assert lookups[0] == 3

    _suspend(client, a["org"]["id"], "suspended")
    assert client.get("/api/v1/lms/ping", headers=h).status_code == 403
    assert client.get("/api/v1/identity/users", headers=h).status_code == 403


def test_with_a_cache_the_lookup_is_reused_within_the_period_and_read_again_after(client, monkeypatch):
    monkeypatch.setenv(gateway.CACHE_SETTING, "5")
    a = register_and_login(client, slug="gc-on", academy_type="dance-academy")
    h = auth(a["token"])
    lookups = _counting(monkeypatch, "_entitlement")
    statuses = _counting(monkeypatch, "_organisation_status")
    for _ in range(3):
        assert client.get("/api/v1/lms/ping", headers=h).status_code == 200
        assert client.get("/api/v1/identity/users", headers=h).status_code == 200
    assert (lookups[0], statuses[0]) == (1, 1)

    # a suspension inside the period is not seen yet: that is the price of the setting, bounded by it
    _suspend(client, a["org"]["id"], "suspended")
    assert client.get("/api/v1/lms/ping", headers=h).status_code == 200
    # once the period is over, the gate reads the database again and refuses
    _later(monkeypatch, 6)
    assert client.get("/api/v1/lms/ping", headers=h).status_code == 403
    assert client.get("/api/v1/identity/users", headers=h).status_code == 403
    assert (lookups[0], statuses[0]) == (2, 2)


def test_each_user_has_their_own_answer(client, monkeypatch):
    """The user's status is part of the answer, so one user's cached answer is never another's."""
    monkeypatch.setenv(gateway.CACHE_SETTING, "5")
    a = register_and_login(client, slug="gc-users", academy_type="dance-academy")
    b = register_and_login(client, slug="gc-users-2", academy_type="dance-academy")
    lookups = _counting(monkeypatch, "_entitlement")
    for token in (a["token"], b["token"], a["token"], b["token"]):
        assert client.get("/api/v1/lms/ping", headers=auth(token)).status_code == 200
    assert lookups[0] == 2


def test_the_setting_is_capped_so_a_typo_cannot_delay_a_suspension_for_hours(monkeypatch):
    monkeypatch.setenv(gateway.CACHE_SETTING, "86400")
    assert gateway.cache_seconds() == gateway.MAX_CACHE_SECONDS == 300
    monkeypatch.setenv(gateway.CACHE_SETTING, "2.5")
    assert gateway.cache_seconds() == 2.5


def test_the_cache_is_bounded(monkeypatch):
    monkeypatch.setattr(gateway, "MAX_CACHE_ENTRIES", 3)
    for i in range(5):
        gateway._remember(("status", f"org-{i}", None), "active", 5)
    assert len(gateway._cache) <= 3
