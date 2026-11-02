"""Module settings from AMC_VENDOR_SUPPORT_* environment keys (config/env.example). Read on every call so a deployment
or a test can change them without restarting the module. A bad value is a deployment error (ValueError), never a
domain error that an API layer could report to a caller as their own invalid request."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

CONTRACT_NUMBER_PREFIX_KEY = "AMC_VENDOR_SUPPORT_CONTRACT_NUMBER_PREFIX"
ENGAGEMENT_NUMBER_PREFIX_KEY = "AMC_VENDOR_SUPPORT_ENGAGEMENT_NUMBER_PREFIX"
EXPIRY_WINDOW_DAYS_KEY = "AMC_VENDOR_SUPPORT_EXPIRY_WINDOW_DAYS"
DEFAULT_CURRENCY_KEY = "AMC_VENDOR_SUPPORT_DEFAULT_CURRENCY"

# Defaults are the values in config/env.example.
DEFAULT_CONTRACT_NUMBER_PREFIX = "AMC"
DEFAULT_ENGAGEMENT_NUMBER_PREFIX = "AVS"
DEFAULT_EXPIRY_WINDOW_DAYS = 60
DEFAULT_DEFAULT_CURRENCY = "INR"

# GET /stats/contracts-expiring: within_days is between 1 and 366.
MIN_WINDOW_DAYS, MAX_WINDOW_DAYS = 1, 366


@dataclass(frozen=True)
class ModuleSettings:
    contract_number_prefix: str
    engagement_number_prefix: str
    expiry_window_days: int
    default_currency: str


def _text(key: str, default: str) -> str:
    """Surrounding spaces removed; unset or blank means the default."""
    raw = os.environ.get(key)
    if raw is None or raw.strip() == "":
        return default
    return raw.strip()


def _window(key: str, default: int) -> int:
    raw = _text(key, str(default))
    try:
        value = int(raw)
    except ValueError:
        raise ValueError(f"{key} must be a whole number, got {raw!r}") from None
    if not MIN_WINDOW_DAYS <= value <= MAX_WINDOW_DAYS:
        raise ValueError(f"{key} must be between {MIN_WINDOW_DAYS} and {MAX_WINDOW_DAYS}, got {raw!r}")
    return value


def _currency(key: str, default: str) -> str:
    value = _text(key, default)
    if not re.fullmatch(r"[A-Z]{3}", value):
        raise ValueError(f"{key} must be an ISO 4217 code such as INR, got {value!r}")
    return value


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        contract_number_prefix=_text(CONTRACT_NUMBER_PREFIX_KEY, DEFAULT_CONTRACT_NUMBER_PREFIX),
        engagement_number_prefix=_text(ENGAGEMENT_NUMBER_PREFIX_KEY, DEFAULT_ENGAGEMENT_NUMBER_PREFIX),
        expiry_window_days=_window(EXPIRY_WINDOW_DAYS_KEY, DEFAULT_EXPIRY_WINDOW_DAYS),
        default_currency=_currency(DEFAULT_CURRENCY_KEY, DEFAULT_DEFAULT_CURRENCY),
    )
