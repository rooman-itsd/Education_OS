"""Organisation-wide defaults from FACILITY_BOOKING_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without a restart of the module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, tzinfo
from zoneinfo import ZoneInfo

from ..domain.rules import Rules


@dataclass(frozen=True)
class ModuleSettings:
    max_days_ahead: int
    default_slot_minutes: int
    no_show_grace_minutes: int
    max_series_occurrences: int
    reminder_minutes_before: int
    timezone: str

    @property
    def tz(self) -> tzinfo:
        return UTC if self.timezone.upper() == "UTC" else ZoneInfo(self.timezone)

    def default_rules(self) -> Rules:
        return Rules(slot_minutes=self.default_slot_minutes, max_days_ahead=self.max_days_ahead)


def _int(key: str, default: int) -> int:
    return int(os.environ.get(f"FACILITY_BOOKING_{key}", default))


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        max_days_ahead=_int("MAX_DAYS_AHEAD", 90),
        default_slot_minutes=_int("DEFAULT_SLOT_MINUTES", 30),
        no_show_grace_minutes=_int("NO_SHOW_GRACE_MINUTES", 15),
        max_series_occurrences=_int("MAX_SERIES_OCCURRENCES", 52),
        reminder_minutes_before=_int("REMINDER_MINUTES_BEFORE", 60),
        timezone=os.environ.get("FACILITY_BOOKING_TIMEZONE", "UTC"),
    )
