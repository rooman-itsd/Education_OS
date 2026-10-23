"""Module settings from FEES_ACCOUNTS_* environment variables (documented in config/env.example). Read on every call
so tests and operators can change them without a restart."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"FEES_ACCOUNTS_{key}", default).strip()


@dataclass(frozen=True)
class ModuleSettings:
    payment_adapter_url: str
    payment_return_url: str
    invoice_number_prefix: str
    receipt_number_prefix: str
    bulk_invoice_max: int
    academic_year_start_month: int
    fine_due_days: int


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        payment_adapter_url=_env("PAYMENT_ADAPTER_URL").rstrip("/"),
        payment_return_url=_env("PAYMENT_RETURN_URL"),
        invoice_number_prefix=_env("INVOICE_NUMBER_PREFIX", "INV"),
        receipt_number_prefix=_env("RECEIPT_NUMBER_PREFIX", "RCT"),
        bulk_invoice_max=int(_env("BULK_INVOICE_MAX", "5000")),
        academic_year_start_month=int(_env("ACADEMIC_YEAR_START_MONTH", "6")),
        fine_due_days=int(_env("FINE_DUE_DAYS", "15")),
    )
