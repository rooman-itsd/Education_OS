"""Scheduler settings from the environment (config/env.example), each bounded."""

from __future__ import annotations

import os
from dataclasses import dataclass


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


def _flag(name: str, default: bool) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if raw == "":
        return default
    if raw not in ("true", "false"):
        raise ValueError(f"{name} must be true or false, not {raw!r}")
    return raw == "true"


@dataclass(frozen=True)
class SchedulerConfig:
    enabled: bool = True
    redis_url: str = "redis://localhost:6379/1"
    tick_interval_s: int = 30
    run_timeout_s: int = 900
    default_catch_up: str = "once"
    catch_up_horizon_s: int = 86_400
    run_retention_days: int = 90

    @classmethod
    def from_env(cls) -> SchedulerConfig:
        catch_up = os.environ.get("SCHEDULER_DEFAULT_CATCH_UP", "once").strip() or "once"
        if catch_up not in ("once", "never"):
            raise ValueError(f"SCHEDULER_DEFAULT_CATCH_UP must be once or never, not {catch_up!r}")
        return cls(
            enabled=_flag("SCHEDULER_ENABLED", True),
            redis_url=os.environ.get("SCHEDULER_REDIS_URL", "redis://localhost:6379/1"),
            tick_interval_s=_int("SCHEDULER_TICK_INTERVAL_S", 30, 1, 3600),
            run_timeout_s=_int("SCHEDULER_RUN_TIMEOUT_S", 900, 10, 86_400),
            default_catch_up=catch_up,
            catch_up_horizon_s=_int("SCHEDULER_CATCH_UP_HORIZON_S", 86_400, 60, 30 * 86_400),
            run_retention_days=_int("SCHEDULER_RUN_RETENTION_DAYS", 90, 1, 3650),
        )
