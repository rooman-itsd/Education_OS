"""Module settings from E_OFFICE_* environment variables (documented in config/env.example). Read on every call so
tests and operators can change them without a restart."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_DUE_DAYS = {"normal": 7, "urgent": 2, "immediate": 1}
MAX_DUE_DAYS = 365


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"E_OFFICE_{key}", default).strip()


def _days(priority: str) -> int:
    """Days a file may stay with one holder at this priority. An unset, unreadable or out-of-range value falls back to
    the default, so a typo never makes every file overdue at once."""
    raw = _env(f"DEFAULT_DUE_DAYS_{priority.upper()}")
    try:
        value = int(raw)
    except ValueError:
        return DEFAULT_DUE_DAYS[priority]
    return value if 0 <= value <= MAX_DUE_DAYS else DEFAULT_DUE_DAYS[priority]


@dataclass(frozen=True)
class ModuleSettings:
    default_due_days: dict[str, int]


def load_settings() -> ModuleSettings:
    return ModuleSettings(default_due_days={p: _days(p) for p in DEFAULT_DUE_DAYS})
