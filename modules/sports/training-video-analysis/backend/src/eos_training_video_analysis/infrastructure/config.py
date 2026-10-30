"""Organisation-wide defaults from TRAINING_VIDEO_ANALYSIS_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import timedelta, timezone

_OFFSET = re.compile(r"^([+-])(\d{2}):(\d{2})$")


@dataclass(frozen=True)
class ModuleSettings:
    local_timezone: timezone


def _env(key: str, default: str) -> str:
    return os.environ.get(f"TRAINING_VIDEO_ANALYSIS_{key}", default)


def _offset(value: str) -> timezone:
    """A fixed UTC offset such as +05:30. A fixed offset needs no timezone database (tzdata is not on the approved
    stack and Windows has none), at the cost of not following daylight-saving changes."""
    m = _OFFSET.match(value.strip())
    if not m:
        raise ValueError(f"TRAINING_VIDEO_ANALYSIS_UTC_OFFSET must look like +05:30, not {value!r}")
    sign = -1 if m.group(1) == "-" else 1
    return timezone(sign * timedelta(hours=int(m.group(2)), minutes=int(m.group(3))))


def load_settings() -> ModuleSettings:
    return ModuleSettings(local_timezone=_offset(_env("UTC_OFFSET", "+05:30")))
