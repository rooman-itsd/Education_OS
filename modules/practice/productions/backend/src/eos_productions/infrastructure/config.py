"""Organisation-wide defaults from PRODUCTIONS_* environment keys (config/env.example). Read on every call so
a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os

from ..domain.rules import ProductionRules


def _int(key: str, default: int) -> int:
    raw = os.environ.get(f"PRODUCTIONS_{key}")
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if value > 0 else default


def load_settings() -> ProductionRules:
    return ProductionRules(
        calendar_window_days=_int("CALENDAR_WINDOW_DAYS", 60),
        min_preparation_days=_int("MIN_PREPARATION_DAYS", 7),
        max_run_hours=_int("MAX_RUN_HOURS", 72),
        default_call_minutes=_int("DEFAULT_CALL_MINUTES", 60),
    )
