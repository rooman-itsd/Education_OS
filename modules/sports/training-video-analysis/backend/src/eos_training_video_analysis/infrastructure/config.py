"""Organisation-wide defaults from TRAINING_VIDEO_ANALYSIS_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSettings:
    timezone: str


def _env(key: str, default: str) -> str:
    return os.environ.get(f"TRAINING_VIDEO_ANALYSIS_{key}", default)


def load_settings() -> ModuleSettings:
    return ModuleSettings(timezone=_env("TIMEZONE", "Asia/Kolkata"))
