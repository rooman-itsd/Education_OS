"""Buckets in Redis, one hash per key, refilled and taken from atomically by a Lua script, so every API process
behind the proxy counts against the same limits. Keys expire once the bucket would be full again.

A Redis that cannot be reached fails open: the request passes and the failure is logged. Losing rate limiting
for a while is better than refusing every request because the cache is down."""

from __future__ import annotations

import logging

from ..domain.bucket import Limit

log = logging.getLogger("eos.gateway")

PREFIX = "eos:gateway:bucket:"

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


class RedisStore:
    def __init__(self, client) -> None:
        self._client = client
        self._take = client.register_script(_TAKE)

    @classmethod
    def from_url(cls, url: str) -> RedisStore:
        import redis

        return cls(redis.Redis.from_url(url, socket_timeout=0.5, socket_connect_timeout=0.5))

    def take(self, key: str, limit: Limit, now: float) -> float | None:
        ttl = int(limit.seconds_to_full) + 1
        try:
            allowed, wait = self._take(keys=[PREFIX + key], args=[limit.burst, limit.refill_per_second, now, ttl])
        except Exception as e:  # any client error: fail open, say so
            log.warning("rate limit store unavailable, allowing request: %s", e)
            return None
        return None if int(allowed) == 1 else float(wait)
