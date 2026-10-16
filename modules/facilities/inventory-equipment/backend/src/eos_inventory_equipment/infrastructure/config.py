"""Organisation-wide defaults from INVENTORY_EQUIPMENT_* environment keys (config/env.example).
Read on every call so a deployment or a test can change them without restarting the module."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ..domain.rules import LoanRules


@dataclass(frozen=True)
class ModuleSettings:
    default_max_loan_days: int
    due_reminder_hours: int
    pickup_expiry_hours: int
    max_open_loans_per_person: int

    def default_rules(self) -> LoanRules:
        return LoanRules(max_loan_days=self.default_max_loan_days)


def _int(key: str, default: int) -> int:
    return int(os.environ.get(f"INVENTORY_EQUIPMENT_{key}", default))


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        default_max_loan_days=_int("DEFAULT_MAX_LOAN_DAYS", 14),
        due_reminder_hours=_int("DUE_REMINDER_HOURS", 24),
        pickup_expiry_hours=_int("PICKUP_EXPIRY_HOURS", 48),
        max_open_loans_per_person=_int("MAX_OPEN_LOANS_PER_PERSON", 3),
    )
