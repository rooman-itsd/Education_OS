"""Module-local configuration. Keys are BILLING_*, documented in config/env.example. Read from the environment on
every call so a test or a redeploy never sees a stale value."""

from __future__ import annotations

import os
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from ..domain import gst


@dataclass(frozen=True)
class Supplier:
    gstin: str
    name: str
    address: str
    state_code: str


@dataclass(frozen=True)
class InvoicingConfig:
    supplier: Supplier | None  # None: no supplier GSTIN configured, so invoices carry no tax (dev, pilots)
    gst_rate: Decimal
    sac_code: str
    prefix: str


def invoicing() -> InvoicingConfig:
    """Raises gst.GstError when a value that is set is not valid: invoices are never issued on a bad registration."""
    env = os.environ.get
    raw_rate = (env("BILLING_GST_RATE") or "18").strip()
    try:
        rate = Decimal(raw_rate)
    except InvalidOperation as e:
        raise gst.GstError(f"BILLING_GST_RATE {raw_rate!r} is not a number") from e
    if not Decimal(0) <= rate <= Decimal(100):
        raise gst.GstError("BILLING_GST_RATE must be between 0 and 100")
    sac = gst.validate_sac(env("BILLING_SAC_CODE") or "998315")
    prefix = gst.validate_prefix(env("BILLING_INVOICE_PREFIX") or "EOS")
    supplier = None
    if (env("BILLING_SUPPLIER_GSTIN") or "").strip():
        gstin = gst.validate_gstin(env("BILLING_SUPPLIER_GSTIN"))
        name = (env("BILLING_SUPPLIER_NAME") or "").strip()
        if not name:
            raise gst.GstError("BILLING_SUPPLIER_NAME is required when BILLING_SUPPLIER_GSTIN is set")
        supplier = Supplier(gstin, name, (env("BILLING_SUPPLIER_ADDRESS") or "").strip(), gst.state_code(gstin))
    return InvoicingConfig(supplier, rate, sac, prefix)
