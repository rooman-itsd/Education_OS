"""Token bucket arithmetic. Pure: no clock, no storage, so every store (in-process, Redis) and every test
shares the same rule."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True)
class Limit:
    """`per_minute` requests sustained, with up to `burst` served at once from a full bucket."""

    per_minute: int
    burst: int

    def __post_init__(self) -> None:
        if self.per_minute <= 0 or self.burst <= 0:
            raise ValueError("a limit needs a positive per-minute rate and burst")

    @classmethod
    def of(cls, per_minute: int, burst: int | None = None) -> Limit:
        """Burst defaults to the per-minute figure: a quiet client may spend a whole minute's quota at once."""
        return cls(per_minute, burst or per_minute)

    @property
    def refill_per_second(self) -> float:
        return self.per_minute / 60.0

    @property
    def seconds_to_full(self) -> float:
        """How long an untouched bucket takes to refill completely; after that it is as good as absent."""
        return self.burst / self.refill_per_second


@dataclass(frozen=True)
class Bucket:
    tokens: float
    updated: float  # clock reading of the last refill


def take(bucket: Bucket | None, now: float, limit: Limit) -> tuple[Bucket, float | None]:
    """Refill `bucket` up to `now` and take one token. Returns the bucket to store and None when the request
    is allowed, or the seconds until the next token when it is not (the bucket then keeps its refill only).
    A missing bucket is a full one; a clock that went backwards refills nothing."""
    if bucket is None:
        tokens = float(limit.burst)
    else:
        elapsed = max(0.0, now - bucket.updated)
        tokens = min(float(limit.burst), bucket.tokens + elapsed * limit.refill_per_second)
    if tokens >= 1.0:
        return Bucket(tokens - 1.0, now), None
    return Bucket(tokens, now), (1.0 - tokens) / limit.refill_per_second


def retry_after(wait: float) -> int:
    """The Retry-After header value: whole seconds, at least one."""
    return max(1, math.ceil(wait))
