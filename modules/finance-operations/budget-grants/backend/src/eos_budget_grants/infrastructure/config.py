"""Module settings from BUDGET_GRANTS_* environment variables (documented in config/env.example). Read on every call
so tests and operators can change them without a restart."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"BUDGET_GRANTS_{key}", default).strip()


def _ints(raw: str) -> tuple[int, ...]:
    return tuple(sorted({int(x) for x in raw.split(",") if x.strip()}))


@dataclass(frozen=True)
class ModuleSettings:
    financial_year_start_month: int
    alert_percents: tuple[int, ...]
    salary_budget_head_code: str
    uc_reminder_days: tuple[int, ...]


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        financial_year_start_month=int(_env("FINANCIAL_YEAR_START_MONTH", "4")),
        alert_percents=_ints(_env("ALERT_PERCENTS", "80,100")),
        salary_budget_head_code=_env("SALARY_BUDGET_HEAD_CODE", "SALARIES"),
        uc_reminder_days=_ints(_env("UC_REMINDER_DAYS", "30,7")),
    )
