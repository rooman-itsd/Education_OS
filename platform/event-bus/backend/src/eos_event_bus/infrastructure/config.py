"""Relay settings from the environment (config/env.example). Every value is bounded: a typo must not make the
relay spin, claim the whole table at once, or never dead-letter."""

from __future__ import annotations

import os
from dataclasses import dataclass

TRANSPORTS = ("inprocess",)


def _int(name: str, default: int, low: int, high: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as e:
        raise ValueError(f"{name} must be a whole number, not {raw!r}") from e
    if not low <= value <= high:
        raise ValueError(f"{name} must be between {low} and {high}, not {value}")
    return value


@dataclass(frozen=True)
class EventBusConfig:
    transport: str = "inprocess"
    poll_interval_ms: int = 1000
    batch_size: int = 100
    max_attempts: int = 8
    retry_cap_s: int = 300
    stall_threshold_s: int = 300
    retention_days: int = 30

    @classmethod
    def from_env(cls) -> EventBusConfig:
        transport = os.environ.get("EVENT_BUS_TRANSPORT", "inprocess").strip() or "inprocess"
        if transport not in TRANSPORTS:
            raise ValueError(f"EVENT_BUS_TRANSPORT must be one of {', '.join(TRANSPORTS)}, not {transport!r}")
        return cls(
            transport=transport,
            poll_interval_ms=_int("EVENT_BUS_POLL_INTERVAL_MS", 1000, 50, 60_000),
            batch_size=_int("EVENT_BUS_BATCH_SIZE", 100, 1, 1000),
            max_attempts=_int("EVENT_BUS_MAX_ATTEMPTS", 8, 1, 50),
            retry_cap_s=_int("EVENT_BUS_RETRY_CAP_S", 300, 1, 86_400),
            stall_threshold_s=_int("EVENT_BUS_STALL_THRESHOLD_S", 300, 10, 86_400),
            retention_days=_int("EVENT_BUS_RETENTION_DAYS", 30, 1, 3650),
        )
