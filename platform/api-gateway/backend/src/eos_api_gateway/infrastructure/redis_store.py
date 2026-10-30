"""Buckets in Redis, one hash per key, refilled and taken from atomically by a Lua script, so every API process
behind the proxy counts against the same limits. Keys expire once the bucket would be full again.

A Redis that cannot be reached fails open: the request passes and the failure is logged. Losing rate limiting
for a while is better than refusing every request because the cache is down. It also fails fast: a short
connect and read timeout, no client retries, and after a failure the store is not asked again for
`RETRY_AFTER_FAILURE` seconds, so a Redis outage costs one request at most ~0.25 s every 30 s instead of every
request ~1.5 s."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable

from ..domain.bucket import Limit

log = logging.getLogger("eos.gateway")

PREFIX = "eos:gateway:bucket:"
CONNECT_TIMEOUT = 0.1  # seconds; Redis sits next to the API, a healthy one answers in well under a millisecond
READ_TIMEOUT = 0.25
RETRY_AFTER_FAILURE = 30.0  # seconds during which a failed store is skipped (requests pass unmetered)

# KEYS[1] bucket; ARGV: burst, refill per second, now, ttl seconds. Returns {allowed, wait}.
_TAKE = """
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens'))
local updated = tonumber(redis.call('HGET', KEYS[1], 'updated'))
local burst, rate, now = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
if tokens == nil or updated == nil then
  tokens, updated = burst, now
end
local elapsed = now - updated
if elapsed < 0 then elapsed = 0 end
tokens = math.min(burst, tokens + elapsed * rate)
local allowed, wait = 1, 0
if tokens >= 1 then
  tokens = tokens - 1
else
  allowed, wait = 0, (1 - tokens) / rate
end
redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated', now)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
return {allowed, tostring(wait)}
"""

# Gives one token back (a take that did not count), up to the burst. KEYS[1] bucket; ARGV: burst, rate, now, ttl.
_REFUND = """
local tokens = tonumber(redis.call('HGET', KEYS[1], 'tokens'))
local updated = tonumber(redis.call('HGET', KEYS[1], 'updated'))
if tokens == nil or updated == nil then
  return 0
end
local burst, rate, now = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
local elapsed = now - updated
if elapsed < 0 then elapsed = 0 end
tokens = math.min(burst, math.min(burst, tokens + elapsed * rate) + 1)
redis.call('HSET', KEYS[1], 'tokens', tokens, 'updated', now)
redis.call('EXPIRE', KEYS[1], tonumber(ARGV[4]))
return 1
"""


class RedisStore:
    def __init__(self, client, clock: Callable[[], float] = time.monotonic) -> None:
        self._client = client
        self._take = client.register_script(_TAKE)
        self._refund = client.register_script(_REFUND)
        self._clock = clock
        self._down_until = 0.0

    @classmethod
    def from_url(cls, url: str) -> RedisStore:
        import redis
        from redis.backoff import NoBackoff
        from redis.retry import Retry

        return cls(
            redis.Redis.from_url(
                url,
                socket_timeout=READ_TIMEOUT,
                socket_connect_timeout=CONNECT_TIMEOUT,
                retry=Retry(NoBackoff(), 0),  # the client's default retries with backoff would hold the request
            )
        )

    def take(self, key: str, limit: Limit, now: float) -> float | None:
        if self._clock() < self._down_until:
            return None  # failed recently: fail open without waiting on it again
        ttl = int(limit.seconds_to_full) + 1
        try:
            allowed, wait = self._take(keys=[PREFIX + key], args=[limit.burst, limit.refill_per_second, now, ttl])
        except Exception as e:  # any client error: fail open, say so, and leave Redis alone for a while
            self._down_until = self._clock() + RETRY_AFTER_FAILURE
            log.warning("rate limit store unavailable, allowing requests for %.0fs: %s", RETRY_AFTER_FAILURE, e)
            return None
        return None if int(allowed) == 1 else float(wait)

    def refund(self, key: str, limit: Limit, now: float) -> None:
        if self._clock() < self._down_until:
            return
        ttl = int(limit.seconds_to_full) + 1
        try:
            self._refund(keys=[PREFIX + key], args=[limit.burst, limit.refill_per_second, now, ttl])
        except Exception as e:  # same policy as take: fail open, say so, leave Redis alone for a while
            self._down_until = self._clock() + RETRY_AFTER_FAILURE
            log.warning("rate limit store unavailable, allowing requests for %.0fs: %s", RETRY_AFTER_FAILURE, e)
