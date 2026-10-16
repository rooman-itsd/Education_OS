"""Organisation-wide defaults from ACADEMIC_MANAGEMENT_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without a restart of the module."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..domain.errors import DomainRuleError
from ..domain.values import require_number

MAX_WEEKLY_CONTACT_HOURS_KEY = "ACADEMIC_MANAGEMENT_MAX_WEEKLY_CONTACT_HOURS"
DEFAULT_MAX_WEEKLY_CONTACT_HOURS = Decimal(18)  # config/env.example


@dataclass(frozen=True)
class ModuleSettings:
    max_weekly_contact_hours: Decimal


def _number(key: str, default: Decimal) -> Decimal:
    """A finite number of at least 0. A bad value is a deployment error (ValueError), never a domain error that
    an API layer could report to a caller as their own invalid request."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    try:
        return require_number(Decimal(raw.strip()), key, minimum=0)
    except InvalidOperation:
        raise ValueError(f"{key} must be a number, got {raw!r}") from None
    except DomainRuleError as err:
        raise ValueError(f"{key}: {err.message}, got {raw!r}") from err


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        max_weekly_contact_hours=_number(MAX_WEEKLY_CONTACT_HOURS_KEY, DEFAULT_MAX_WEEKLY_CONTACT_HOURS),
    )
