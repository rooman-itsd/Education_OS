"""Organisation-wide settings from SPORTS_FACILITIES_* environment keys (config/env.example).
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
        """The institution's local time zone: operating hours, usage dates and utilisation are read in it."""
        return UTC if self.timezone.upper() == "UTC" else ZoneInfo(self.timezone)


def load_settings() -> ModuleSettings:
    return ModuleSettings(timezone=os.environ.get("SPORTS_FACILITIES_TIMEZONE", "Asia/Kolkata"))
