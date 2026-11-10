"""In-process buckets: an ordered dict under a lock. Right for one API process; with several, each process
counts on its own (set EOS_REDIS_URL to share). Full buckets are dropped now and then so idle clients cost
nothing, and the store holds at most `max_buckets`: past that the least recently used bucket is dropped, so a
flood of fresh keys (addresses, accounts) cannot grow the process without bound. A dropped bucket is a full one
when it comes back, which only ever favours that client."""

from __future__ import annotations

import threading
from collections import OrderedDict

from ..domain.bucket import Bucket, Limit, give_back, take

_PRUNE_EVERY = 4096
MAX_BUCKETS = 50_000  # ~10 MB at most; a school's clients, users and accounts in an hour fit with room to spare


class MemoryStore:
    def __init__(self, max_buckets: int = MAX_BUCKETS) -> None:
        if max_buckets <= 0:
            raise ValueError("max_buckets must be positive")
        # key -> (bucket, when it is full again), least recently used first
        self._buckets: OrderedDict[str, tuple[Bucket, float]] = OrderedDict()
        self._lock = threading.Lock()
        self._ops = 0
        self.max_buckets = max_buckets

    def __len__(self) -> int:
        return len(self._buckets)

    async def take(self, key: str, limit: Limit, now: float) -> float | None:
        with self._lock:
            current = self._buckets.get(key)
            bucket, wait = take(current[0] if current else None, now, limit)
            self._buckets[key] = (bucket, now + limit.seconds_to_full)
            self._buckets.move_to_end(key)
            self._ops += 1
            if self._ops % _PRUNE_EVERY == 0:
                self._prune(now)
            while len(self._buckets) > self.max_buckets:
                self._buckets.popitem(last=False)  # the least recently used
            return wait

    async def refund(self, key: str, limit: Limit, now: float) -> None:
        with self._lock:
            current = self._buckets.get(key)
            if current is None:
                return  # pruned or evicted (as good as full): nothing to give back
            self._buckets[key] = (give_back(current[0], now, limit), now + limit.seconds_to_full)

    def _prune(self, now: float) -> None:
        for key in [k for k, (_, full_at) in self._buckets.items() if full_at <= now]:
            del self._buckets[key]
