"""Module settings from SLA_MANAGEMENT_* environment keys (config/env.example). Read on every call so a deployment or
a test can change them without restarting the module. A bad value is a deployment error (ValueError), never a domain
error that an API layer could report to a caller as their own invalid request."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_WARNING_PERCENT_KEY = "SLA_MANAGEMENT_DEFAULT_WARNING_PERCENT"
MAX_ESCALATION_LEVELS_KEY = "SLA_MANAGEMENT_MAX_ESCALATION_LEVELS"
BREACH_LIST_LIMIT_KEY = "SLA_MANAGEMENT_BREACH_LIST_LIMIT"

# Defaults are the values in config/env.example.
DEFAULT_WARNING_PERCENT = 75
DEFAULT_MAX_ESCALATION_LEVELS = 3
DEFAULT_BREACH_LIST_LIMIT = 10

# Ranges: warning_percent is 1 to 99 in the contract; GET /stats/breaches takes limit 1 to 50. A policy has at most
# LEVELS_CAP escalation levels whatever the setting, which is also the request schema's bound.
WARNING_PERCENT_RANGE = (1, 99)
LEVELS_CAP = 10
ESCALATION_LEVELS_RANGE = (0, LEVELS_CAP)
BREACH_LIST_RANGE = (1, 50)


@dataclass(frozen=True)
class ModuleSettings:
    default_warning_percent: int
    max_escalation_levels: int
    breach_list_limit: int


def _whole(key: str, default: int, bounds: tuple[int, int]) -> int:
    """Surrounding spaces removed; unset or blank means the default."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw.strip())
    except ValueError:
        raise ValueError(f"{key} must be a whole number, got {raw!r}") from None
    low, high = bounds
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}, got {raw!r}")
    return value


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        default_warning_percent=_whole(DEFAULT_WARNING_PERCENT_KEY, DEFAULT_WARNING_PERCENT, WARNING_PERCENT_RANGE),
        max_escalation_levels=_whole(MAX_ESCALATION_LEVELS_KEY, DEFAULT_MAX_ESCALATION_LEVELS, ESCALATION_LEVELS_RANGE),
        breach_list_limit=_whole(BREACH_LIST_LIMIT_KEY, DEFAULT_BREACH_LIST_LIMIT, BREACH_LIST_RANGE),
    )
