"""Module settings from GRIEVANCE_* environment keys (config/env.example). Read on every call so a deployment or a test
can change them without restarting the module. A bad value is a deployment error (ValueError), never a domain error
that an API layer could report to a caller as their own invalid request.

The day values and the appeal window have no default (docs/prd.md open question 1): empty means "not set", which gives
a case no due date and refuses appeals."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field

from ..domain.cases import DAY_COUNTING, MAX_DAYS, TRACKS

PREFIX_KEY = "GRIEVANCE_CASE_NUMBER_PREFIX"
APPEAL_WINDOW_KEY = "GRIEVANCE_APPEAL_WINDOW_DAYS"
DAY_COUNTING_KEY = "GRIEVANCE_DAY_COUNTING"
DEFAULT_PREFIX = "GRV"
PREFIX_PATTERN = re.compile(r"^[A-Za-z0-9]{1,10}$")


def acknowledge_key(track: str) -> str:
    return f"GRIEVANCE_{track.upper()}_ACKNOWLEDGE_DAYS"


def decide_key(track: str) -> str:
    return f"GRIEVANCE_{track.upper()}_DECIDE_DAYS"


@dataclass(frozen=True)
class ModuleSettings:
    case_number_prefix: str = DEFAULT_PREFIX
    acknowledge_days: dict[str, int | None] = field(default_factory=dict)
    decide_days: dict[str, int | None] = field(default_factory=dict)
    appeal_window_days: int | None = None
    day_counting: str | None = None


def _text(key: str) -> str | None:
    """Surrounding spaces removed; unset or blank means not set."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return None
    return raw.strip()


def _days(key: str) -> int | None:
    raw = _text(key)
    if raw is None:
        return None
    if not (raw.isascii() and raw.isdigit()):
        raise ValueError(f"{key} must be a whole number of days, got {raw!r}")
    value = int(raw)
    if not 1 <= value <= MAX_DAYS:
        raise ValueError(f"{key} must be between 1 and {MAX_DAYS}, got {raw!r}")
    return value


def load_settings() -> ModuleSettings:
    prefix = _text(PREFIX_KEY) or DEFAULT_PREFIX
    if not PREFIX_PATTERN.match(prefix):
        raise ValueError(f"{PREFIX_KEY} must be 1 to 10 letters or digits, got {prefix!r}")
    counting = _text(DAY_COUNTING_KEY)
    if counting is not None:
        counting = counting.lower()
        if counting not in DAY_COUNTING:
            raise ValueError(f"{DAY_COUNTING_KEY} must be calendar or working, got {counting!r}")
    return ModuleSettings(
        case_number_prefix=prefix,
        acknowledge_days={t: _days(acknowledge_key(t)) for t in TRACKS},
        decide_days={t: _days(decide_key(t)) for t in TRACKS},
        appeal_window_days=_days(APPEAL_WINDOW_KEY),
        day_counting=counting,
    )
