"""Organisation-wide defaults from SPORTS_NUTRITION_HEALTH_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSettings:
    default_appointment_minutes: int


def _env(key: str, default: str) -> str:
    return os.environ.get(f"SPORTS_NUTRITION_HEALTH_{key}", default)


def load_settings() -> ModuleSettings:
    return ModuleSettings(default_appointment_minutes=int(_env("DEFAULT_APPOINTMENT_MINUTES", "30")))
