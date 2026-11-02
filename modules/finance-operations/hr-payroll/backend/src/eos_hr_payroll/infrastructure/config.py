"""Module settings from HR_PAYROLL_* environment variables (documented in config/env.example). Read on every call so
tests and operators can change them without a restart. An unreadable or out-of-range value falls back to its default."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"HR_PAYROLL_{key}", default).strip()


def _int(raw: str, default: int, low: int, high: int) -> int:
    try:
        value = int(raw)
    except ValueError:
        return default
    return value if low <= value <= high else default


@dataclass(frozen=True)
class ModuleSettings:
    currency: str
    leave_year_start_month: int
    payroll_due_day: int


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        currency=_env("CURRENCY", "INR") or "INR",
        leave_year_start_month=_int(_env("LEAVE_YEAR_START_MONTH", "1"), 1, 1, 12),
        payroll_due_day=_int(_env("PAYROLL_DUE_DAY", "28"), 28, 1, 31),
    )
