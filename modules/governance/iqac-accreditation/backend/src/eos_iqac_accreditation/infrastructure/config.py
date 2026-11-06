"""Module settings from IQAC_ACCREDITATION_* environment keys (config/env.example). Read on every call so a deployment
or a test can change them without restarting the module. A bad value is a deployment error (ValueError), never a
domain error that an API layer could report to a caller as their own invalid request."""

from __future__ import annotations

import os
from dataclasses import dataclass

DUE_SOON_DAYS_KEY = "IQAC_ACCREDITATION_DUE_SOON_DAYS"

# The default is the value in config/env.example.
DEFAULT_DUE_SOON_DAYS = 14

# Bounds a deployment may set. The window is a widget threshold, not a rule; the upper bound keeps the date sum small.
MIN_DUE_SOON_DAYS, MAX_DUE_SOON_DAYS = 1, 366


@dataclass(frozen=True)
class ModuleSettings:
    due_soon_days: int


def _text(key: str, default: str) -> str:
    """Surrounding spaces removed; unset or blank means the default."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _days(key: str, default: int, low: int, high: int) -> int:
    raw = _text(key, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{key} must be a whole number, got {raw!r}") from None
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}, got {raw!r}")
    return value


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        due_soon_days=_days(DUE_SOON_DAYS_KEY, DEFAULT_DUE_SOON_DAYS, MIN_DUE_SOON_DAYS, MAX_DUE_SOON_DAYS)
    )
