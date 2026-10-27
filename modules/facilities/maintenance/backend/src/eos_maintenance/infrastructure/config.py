"""Organisation-wide defaults from MAINTENANCE_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..domain.rules import PRIORITIES, SlaHours

RESPONSE_DEFAULTS = {"urgent": 1, "high": 4, "medium": 24, "low": 72}
RESOLUTION_DEFAULTS = {"urgent": 8, "high": 48, "medium": 120, "low": 336}


@dataclass(frozen=True)
class ModuleSettings:
    sla: SlaHours
    auto_close_days: int
    reopen_window_days: int
    default_lead_days: int
    default_currency: str


def _int(key: str, default: int) -> int:
    return int(os.environ.get(f"MAINTENANCE_{key}", default))


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        sla=SlaHours(
            response={p: _int(f"SLA_RESPONSE_HOURS_{p.upper()}", RESPONSE_DEFAULTS[p]) for p in PRIORITIES},
            resolution={p: _int(f"SLA_RESOLUTION_HOURS_{p.upper()}", RESOLUTION_DEFAULTS[p]) for p in PRIORITIES},
        ),
        auto_close_days=_int("AUTO_CLOSE_DAYS", 3),
        reopen_window_days=_int("REOPEN_WINDOW_DAYS", 7),
        default_lead_days=_int("DEFAULT_LEAD_DAYS", 3),
        default_currency=os.environ.get("MAINTENANCE_DEFAULT_CURRENCY", "INR"),
    )
