"""Module settings from REGULATORY_REPORTS_* environment keys (config/env.example). Read on every call so a deployment
or a test can change them without restarting the module. A bad value is a deployment error (ValueError), never a
domain error that an API layer could report to a caller as their own invalid request."""

from __future__ import annotations

import os
from dataclasses import dataclass

DUE_SOON_DAYS_KEY = "REGULATORY_REPORTS_DUE_SOON_DAYS"
CALENDAR_MAX_DAYS_KEY = "REGULATORY_REPORTS_CALENDAR_MAX_DAYS"

# Defaults are the values in config/env.example.
DEFAULT_DUE_SOON_DAYS = 30
DEFAULT_CALENDAR_MAX_DAYS = 366

# Bounds a deployment may set. Both are widget limits, not legal values; the upper bounds keep the window and the
# calendar range small enough that no date sum and no calendar query grows without limit.
MIN_DUE_SOON_DAYS, MAX_DUE_SOON_DAYS = 1, 366
MIN_CALENDAR_MAX_DAYS, MAX_CALENDAR_MAX_DAYS = 1, 1096  # up to three years


@dataclass(frozen=True)
class ModuleSettings:
    due_soon_days: int
    calendar_max_days: int


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
        due_soon_days=_days(DUE_SOON_DAYS_KEY, DEFAULT_DUE_SOON_DAYS, MIN_DUE_SOON_DAYS, MAX_DUE_SOON_DAYS),
        calendar_max_days=_days(
            CALENDAR_MAX_DAYS_KEY, DEFAULT_CALENDAR_MAX_DAYS, MIN_CALENDAR_MAX_DAYS, MAX_CALENDAR_MAX_DAYS
        ),
    )
