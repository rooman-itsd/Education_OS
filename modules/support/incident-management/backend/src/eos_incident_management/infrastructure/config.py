"""Module settings from INCIDENT_MANAGEMENT_* environment keys (config/env.example). Read on every call so a
deployment or a test can change them without restarting the module. A bad value is a deployment error (ValueError),
never a domain error that an API layer could report to a caller as their own invalid request."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

INCIDENT_NUMBER_PREFIX_KEY = "INCIDENT_MANAGEMENT_INCIDENT_NUMBER_PREFIX"
PROBLEM_NUMBER_PREFIX_KEY = "INCIDENT_MANAGEMENT_PROBLEM_NUMBER_PREFIX"

# Defaults are the values in config/env.example.
DEFAULT_INCIDENT_NUMBER_PREFIX = "INC"
DEFAULT_PROBLEM_NUMBER_PREFIX = "PRB"

# A number is "<prefix>-<at least six digits>" in a String(40) column: the prefix is letters, digits and inner
# hyphens, at most 20 characters, so the number always fits.
PREFIX_PATTERN = re.compile(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,18}[A-Za-z0-9])?")


@dataclass(frozen=True)
class ModuleSettings:
    incident_number_prefix: str
    problem_number_prefix: str


def _prefix(key: str, default: str) -> str:
    """Surrounding spaces removed; unset or blank means the default."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    value = raw.strip()
    if not PREFIX_PATTERN.fullmatch(value):
        raise ValueError(f"{key} must be 1 to 20 letters, digits or inner hyphens, such as INC, got {value!r}")
    return value


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        incident_number_prefix=_prefix(INCIDENT_NUMBER_PREFIX_KEY, DEFAULT_INCIDENT_NUMBER_PREFIX),
        problem_number_prefix=_prefix(PROBLEM_NUMBER_PREFIX_KEY, DEFAULT_PROBLEM_NUMBER_PREFIX),
    )
