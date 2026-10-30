"""In-process buckets: a dict under a lock. Right for one API process; with several, each process counts on
its own (set EOS_REDIS_URL to share). Full buckets are dropped now and then so idle clients cost nothing."""

from __future__ import annotations

import threading

from ..domain.bucket import Bucket, Limit, give_back, take

_PRUNE_EVERY = 4096


class MemoryStore:
    def __init__(self) -> None:
        self._buckets: dict[str, tuple[Bucket, float]] = {}  # key -> (bucket, when it is full again)
        self._lock = threading.Lock()
        self._ops = 0

    def __len__(self) -> int:
        return len(self._buckets)

    def take(self, key: str, limit: Limit, now: float) -> float | None:
        with self._lock:
            current = self._buckets.get(key)
            bucket, wait = take(current[0] if current else None, now, limit)
            self._buckets[key] = (bucket, now + limit.seconds_to_full)
            self._ops += 1
            if self._ops % _PRUNE_EVERY == 0:
                self._prune(now)
            return wait

    def refund(self, key: str, limit: Limit, now: float) -> None:
        with self._lock:
            current = self._buckets.get(key)
            if current is None:
                return  # pruned (full again): nothing to give back
            self._buckets[key] = (give_back(current[0], now, limit), now + limit.seconds_to_full)

    def _prune(self, now: float) -> None:
        for key in [k for k, (_, full_at) in self._buckets.items() if full_at <= now]:
            del self._buckets[key]
