"""Bucket stores. `store_for(settings)` picks Redis when EOS_REDIS_URL is set (every API process then shares
the same counters), else the in-process store (one process, or local dev and tests)."""

from __future__ import annotations

from ..application.limiter import BucketStore
from ..settings import GatewaySettings
from .memory import MemoryStore


def store_for(settings: GatewaySettings) -> BucketStore:
    if settings.redis_url:
        from .redis_store import RedisStore

        return RedisStore.from_url(settings.redis_url)
    return MemoryStore()


__all__ = ["MemoryStore", "store_for"]
