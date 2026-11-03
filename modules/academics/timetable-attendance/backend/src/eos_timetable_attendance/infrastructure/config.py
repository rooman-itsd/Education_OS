"""Organisation-wide settings from TIMETABLE_ATTENDANCE_* environment keys (config/env.example). Read on every call so
a deployment or a test can change them without a restart of the module. Per-organisation overrides are open question
Q5 of the PRD; until it is answered these apply to every organisation."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..domain.attendance import Policy
from ..domain.errors import DomainRuleError

MARKING_OPENS_BEFORE_MINUTES_KEY = "TIMETABLE_ATTENDANCE_MARKING_OPENS_BEFORE_MINUTES"
MARKING_WINDOW_HOURS_KEY = "TIMETABLE_ATTENDANCE_MARKING_WINDOW_HOURS"
CORRECTION_WINDOW_DAYS_KEY = "TIMETABLE_ATTENDANCE_CORRECTION_WINDOW_DAYS"
SHORTAGE_THRESHOLD_PERCENT_KEY = "TIMETABLE_ATTENDANCE_SHORTAGE_THRESHOLD_PERCENT"

# The values written in config/env.example.
DEFAULT_MARKING_OPENS_BEFORE_MINUTES = 15
DEFAULT_MARKING_WINDOW_HOURS = 24
DEFAULT_CORRECTION_WINDOW_DAYS = 7
DEFAULT_SHORTAGE_THRESHOLD_PERCENT = 75


@dataclass(frozen=True)
class ModuleSettings:
    marking_opens_before_minutes: int
    marking_window_hours: int
    correction_window_days: int
    shortage_threshold_percent: int

    @property
    def policy(self) -> Policy:
        return Policy(
            marking_opens_before_minutes=self.marking_opens_before_minutes,
            marking_window_hours=self.marking_window_hours,
            correction_window_days=self.correction_window_days,
            shortage_threshold_percent=self.shortage_threshold_percent,
        )


def _integer(key: str, default: int) -> int:
    """A whole number from the environment. A bad value is a deployment error (ValueError), never a domain error that
    an API layer could report to a caller as their own invalid request."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return int(raw.strip())
    except ValueError:
        raise ValueError(f"{key} must be a whole number, got {raw!r}") from None


def load_settings() -> ModuleSettings:
    settings = ModuleSettings(
        marking_opens_before_minutes=_integer(MARKING_OPENS_BEFORE_MINUTES_KEY, DEFAULT_MARKING_OPENS_BEFORE_MINUTES),
        marking_window_hours=_integer(MARKING_WINDOW_HOURS_KEY, DEFAULT_MARKING_WINDOW_HOURS),
        correction_window_days=_integer(CORRECTION_WINDOW_DAYS_KEY, DEFAULT_CORRECTION_WINDOW_DAYS),
        shortage_threshold_percent=_integer(SHORTAGE_THRESHOLD_PERCENT_KEY, DEFAULT_SHORTAGE_THRESHOLD_PERCENT),
    )
    try:
        settings.policy  # noqa: B018  the domain policy states the limits (0 or more; threshold 0 to 100)
    except DomainRuleError as err:
        raise ValueError(f"{err.field}: {err.message}") from err
    return settings
