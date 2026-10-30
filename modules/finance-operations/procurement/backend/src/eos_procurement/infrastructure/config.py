"""Module settings from PROCUREMENT_* environment variables (documented in config/env.example). Read on every call so
tests and operators can change them without a restart."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation


def _env(key: str, default: str = "") -> str:
    return os.environ.get(f"PROCUREMENT_{key}", default).strip()


def _amount(raw: str) -> Decimal | None:
    """A limit in rupees, or None when it is not set (the purchase limits have no default)."""
    if not raw:
        return None
    try:
        value = Decimal(raw)
    except InvalidOperation:
        return None
    return value if value.is_finite() and value >= 0 else None


@dataclass(frozen=True)
class ModuleSettings:
    budget_grants_url: str
    direct_purchase_limit: Decimal | None
    quotation_limit: Decimal | None
    invoice_match_tolerance_percent: Decimal


def load_settings() -> ModuleSettings:
    return ModuleSettings(
        budget_grants_url=_env("BUDGET_GRANTS_URL").rstrip("/"),
        direct_purchase_limit=_amount(_env("DIRECT_PURCHASE_LIMIT")),
        quotation_limit=_amount(_env("QUOTATION_LIMIT")),
        invoice_match_tolerance_percent=_amount(_env("INVOICE_MATCH_TOLERANCE_PERCENT", "0")) or Decimal("0"),
    )
