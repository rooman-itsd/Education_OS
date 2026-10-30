"""Organisation-wide defaults from ATHLETE_PERFORMANCE_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSettings:
    trend_steady_percent: float
    timezone: str


def _env(key: str, default: str) -> str:
    return os.environ.get(f"ATHLETE_PERFORMANCE_{key}", default)


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        trend_steady_percent=float(_env("TREND_STEADY_PERCENT", "1")),
        timezone=_env("TIMEZONE", "Asia/Kolkata"),
    )
