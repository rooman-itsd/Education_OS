"""Organisation-wide defaults from TOURNAMENT_EVENTS_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, tzinfo
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class ModuleSettings:
    timezone: str

    @property
    def tz(self) -> tzinfo:
        """The institution's timezone, an IANA name resolved from the host's time-zone database."""
        return UTC if self.timezone.upper() == "UTC" else ZoneInfo(self.timezone)


def _env(key: str, default: str) -> str:
    return os.environ.get(f"TOURNAMENT_EVENTS_{key}", default)


def load_settings() -> ModuleSettings:
    return ModuleSettings(timezone=_env("TIMEZONE", "Asia/Kolkata"))
