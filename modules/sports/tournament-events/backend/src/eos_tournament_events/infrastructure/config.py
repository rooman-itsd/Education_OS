"""Organisation-wide defaults from TOURNAMENT_EVENTS_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, timedelta, timezone, tzinfo
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# Zones that need no time-zone database: a host without one (Windows without tzdata, which is not on the approved
# stack) still resolves them. Asia/Kolkata has kept UTC+05:30 without daylight saving since 1945.
FIXED_ZONES = {"UTC": UTC, "Asia/Kolkata": timezone(timedelta(hours=5, minutes=30), "Asia/Kolkata")}


@dataclass(frozen=True)
class ModuleSettings:
    timezone: str

    @property
    def tz(self) -> tzinfo:
        """The institution's timezone. Any IANA name works where the host has a time-zone database."""
        try:
            return ZoneInfo(self.timezone)
        except ZoneInfoNotFoundError:
            if self.timezone in FIXED_ZONES:
                return FIXED_ZONES[self.timezone]
            raise


def _env(key: str, default: str) -> str:
    return os.environ.get(f"TOURNAMENT_EVENTS_{key}", default)


def load_settings() -> ModuleSettings:
    return ModuleSettings(timezone=_env("TIMEZONE", "Asia/Kolkata"))
