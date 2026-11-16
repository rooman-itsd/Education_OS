"""Module settings from RTI_* environment keys (config/env.example). Read on every call so a deployment or a test can
change them without restarting the module. A bad value is a deployment error (ValueError), never a domain error that
an API layer could report to a caller as their own invalid request.

The three timeline settings have no default: until the governance office confirms them (PRD open question 1) there is
no due date, appeals are refused and responded requests stay responded."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from ..domain.dates import CALENDAR, DAY_COUNTINGS
from ..domain.deadlines import Timelines

PREFIX_KEY = "RTI_REQUEST_NUMBER_PREFIX"
CURRENCY_KEY = "RTI_DEFAULT_CURRENCY"
NEARING_KEY = "RTI_NEARING_DEADLINE_DAYS"
RESPONSE_DAYS_KEY = "RTI_RESPONSE_DAYS"
APPEAL_WINDOW_KEY = "RTI_APPEAL_WINDOW_DAYS"
APPEAL_DECIDE_KEY = "RTI_APPEAL_DECIDE_DAYS"
COUNTING_KEY = "RTI_DAY_COUNTING"

# Defaults are the values in config/env.example.
DEFAULT_PREFIX = "RTI"
DEFAULT_CURRENCY = "INR"
DEFAULT_NEARING_DAYS = 7

# Bounds a deployment may set. The upper bounds keep every date sum small (at most a year), and the widget window is
# not a legal value.
MIN_NEARING_DAYS, MAX_NEARING_DAYS = 1, 366
MIN_TIMELINE_DAYS, MAX_TIMELINE_DAYS = 1, 365
PREFIX_PATTERN = re.compile(r"^[A-Z0-9]{1,10}$")
CURRENCY_PATTERN = re.compile(r"^[A-Z]{3}$")


@dataclass(frozen=True)
class ModuleSettings:
    number_prefix: str
    default_currency: str
    nearing_days: int
    timelines: Timelines


def _text(key: str) -> str | None:
    """Surrounding spaces removed; unset or blank is None."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip()


def _days(key: str, default: int | None, low: int, high: int) -> int | None:
    raw = _text(key)
    if raw is None:
        return default
    if not re.fullmatch(r"[0-9]{1,6}", raw):  # ASCII digits only: int() would also take "١٢" or "-3"
        raise ValueError(f"{key} must be a whole number between {low} and {high}, got {raw!r}")
    value = int(raw)
    if not low <= value <= high:
        raise ValueError(f"{key} must be between {low} and {high}, got {raw!r}")
    return value


def _matching(key: str, default: str, pattern: re.Pattern[str], what: str) -> str:
    raw = _text(key)
    if raw is None:
        return default
    if not pattern.match(raw):
        raise ValueError(f"{key} must be {what}, got {raw!r}")
    return raw


def load_settings() -> ModuleSettings:
    counting = (_text(COUNTING_KEY) or CALENDAR).lower()
    if counting not in DAY_COUNTINGS:
        raise ValueError(f"{COUNTING_KEY} must be one of {', '.join(DAY_COUNTINGS)} (or empty), got {counting!r}")
    return ModuleSettings(
        number_prefix=_matching(PREFIX_KEY, DEFAULT_PREFIX, PREFIX_PATTERN, "1 to 10 capital letters or digits"),
        default_currency=_matching(CURRENCY_KEY, DEFAULT_CURRENCY, CURRENCY_PATTERN, "three capital letters"),
        nearing_days=_days(NEARING_KEY, DEFAULT_NEARING_DAYS, MIN_NEARING_DAYS, MAX_NEARING_DAYS),
        timelines=Timelines(
            response_days=_days(RESPONSE_DAYS_KEY, None, MIN_TIMELINE_DAYS, MAX_TIMELINE_DAYS),
            appeal_window_days=_days(APPEAL_WINDOW_KEY, None, MIN_TIMELINE_DAYS, MAX_TIMELINE_DAYS),
            appeal_decide_days=_days(APPEAL_DECIDE_KEY, None, MIN_TIMELINE_DAYS, MAX_TIMELINE_DAYS),
            counting=counting,
        ),
    )
