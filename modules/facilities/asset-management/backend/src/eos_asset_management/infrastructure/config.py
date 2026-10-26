"""Organisation-wide defaults from ASSET_MANAGEMENT_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class ModuleSettings:
    default_currency: str
    tag_prefix: str
    default_verification_interval_months: int
    verification_due_soon_days: int
    financial_year_start_month: int


def _env(key: str, default: str) -> str:
    return os.environ.get(f"ASSET_MANAGEMENT_{key}", default)


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        default_currency=_env("DEFAULT_CURRENCY", "INR"),
        tag_prefix=_env("TAG_PREFIX", "AST"),
        default_verification_interval_months=int(_env("DEFAULT_VERIFICATION_INTERVAL_MONTHS", "12")),
        verification_due_soon_days=int(_env("VERIFICATION_DUE_SOON_DAYS", "30")),
        financial_year_start_month=int(_env("FINANCIAL_YEAR_START_MONTH", "4")),
    )
