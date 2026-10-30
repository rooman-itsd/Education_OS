"""Token bucket arithmetic and the settings that feed it."""

import pytest
from eos_api_gateway.domain.bucket import Limit, retry_after, take
from eos_api_gateway.infrastructure import MemoryStore
from eos_api_gateway.settings import DEFAULT_TRUSTED_PROXIES, GatewaySettings


def test_a_full_bucket_serves_the_burst_then_refills_at_the_rate():
    limit = Limit(60, 3)  # one token a second, three at once
    bucket = None
    for _ in range(3):
        bucket, wait = take(bucket, 100.0, limit)
        assert wait is None
    bucket, wait = take(bucket, 100.0, limit)
    assert wait == pytest.approx(1.0)
    bucket, wait = take(bucket, 100.5, limit)  # half a token back: still waiting half a second
    assert wait == pytest.approx(0.5)
    bucket, wait = take(bucket, 101.0, limit)
    assert wait is None
    assert bucket.tokens == pytest.approx(0.0)


def test_refill_never_exceeds_the_burst_and_a_backwards_clock_adds_nothing():
    limit = Limit(60, 2)
    bucket, _ = take(None, 100.0, limit)
    bucket, wait = take(bucket, 10_000.0, limit)
    assert wait is None and bucket.tokens == pytest.approx(1.0)
    bucket, wait = take(bucket, 50.0, limit)  # clock went backwards: no refill, one token left to take
    assert wait is None and bucket.tokens == pytest.approx(0.0)


def test_retry_after_is_whole_seconds_and_at_least_one():
    assert retry_after(0.01) == 1 and retry_after(1.0) == 1 and retry_after(1.2) == 2


def test_limit_of_defaults_burst_to_the_rate_and_refuses_zero():
    assert Limit.of(120) == Limit(120, 120) and Limit.of(120, 10) == Limit(120, 10)
    with pytest.raises(ValueError, match="positive"):
        Limit(0, 1)


def test_memory_store_keys_buckets_apart_and_prunes_full_ones():
    store = MemoryStore()
    limit = Limit(60, 1)
    assert store.take("a", limit, 0.0) is None and store.take("a", limit, 0.0) == pytest.approx(1.0)
    assert store.take("b", limit, 0.0) is None  # another key, its own bucket
    assert len(store) == 2
    store._prune(0.5)  # nobody is full yet
    assert len(store) == 2
    store._prune(1.0)  # both full again: as good as absent
    assert len(store) == 0


def test_settings_from_env_reads_every_key_and_keeps_defaults():
    s = GatewaySettings.from_env({})
    assert s.security_headers and s.rate_limit and s.redis_url is None
    assert s.ip == Limit(600, 600) and s.organisation == Limit(3000, 3000) and s.auth == Limit(20, 20)
    assert s.trusted_proxies == DEFAULT_TRUSTED_PROXIES
    s = GatewaySettings.from_env(
        {
            "EOS_SECURITY_HEADERS": "false",
            "EOS_RATE_LIMIT_ENABLED": "0",
            "EOS_RATE_LIMIT_IP_PER_MINUTE": "100",
            "EOS_RATE_LIMIT_IP_BURST": "10",
            "EOS_RATE_LIMIT_ORG_PER_MINUTE": "900",
            "EOS_RATE_LIMIT_AUTH_PER_MINUTE": "5",
            "EOS_RATE_LIMIT_AUTH_BURST": "3",
            "EOS_TRUSTED_PROXIES": "192.0.2.1, 198.51.100.0/24",
            "EOS_REDIS_URL": "redis://cache:6379/1",
            "EOS_HSTS_MAX_AGE": "600",
        }
    )
    assert not s.security_headers and not s.rate_limit and s.hsts_max_age == 600
    assert s.ip == Limit(100, 10) and s.organisation == Limit(900, 900) and s.auth == Limit(5, 3)
    assert s.trusted_proxies == ("192.0.2.1", "198.51.100.0/24") and s.redis_url == "redis://cache:6379/1"


@pytest.mark.parametrize("env", [{"EOS_RATE_LIMIT_IP_PER_MINUTE": "ten"}, {"EOS_RATE_LIMIT_ORG_PER_MINUTE": "0"}])
def test_settings_refuse_a_limit_that_is_not_a_positive_number(env):
    with pytest.raises(RuntimeError, match="EOS_RATE_LIMIT_"):
        GatewaySettings.from_env(env)
