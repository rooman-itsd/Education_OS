"""Request bodies of contracts/openapi.yaml. Strict: unknown fields are refused, except readOnly fields of a schema
that is both input and output, which are accepted and ignored. Money stays a decimal string here; the domain parses
it exactly."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MONEY = r"^-?[0-9]+(\.[0-9]{1,2})?$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Item(Strict):
    description: str = Field(min_length=1, max_length=500)
    specification: str | None = None
    quantity: float = Field(gt=0)
    unit: str = Field(min_length=1, max_length=40)
    unit_price: str | None = Field(default=None, pattern=MONEY)
    tax_percent: float | None = Field(default=None, ge=0)


class BankAccount(Strict):
    account_number: str | None = Field(default=None, max_length=40)
    account_last4: str | None = None  # readOnly: accepted and ignored
    ifsc: str | None = Field(default=None, max_length=11)


class VendorInput(Strict):
    id: str | None = None  # readOnly fields of Vendor, accepted and ignored
    organisation_id: str | None = None
    status: str | None = None
    status_reason: str | None = None
    orders_count: int | None = None
    orders_value: str | None = None
    name: str = Field(min_length=1, max_length=200)
    categories: list[str] = Field(min_length=1)
    contact_name: str | None = Field(default=None, max_length=200)
    email: str | None = Field(default=None, max_length=254, pattern=r"^$|^[^@\s]+@[^@\s]+\.[^@\s]+$")
    phone: str | None = Field(default=None, max_length=40)
    address: str | None = None
    gstin: str | None = Field(default=None, max_length=15)
    pan: str | None = Field(default=None, max_length=10)
    msme_registration: str | None = Field(default=None, max_length=40)
    bank_account: BankAccount | None = None


class VendorStatusInput(Strict):
    status: Literal["approved", "suspended", "blacklisted"]
    reason: str = Field(min_length=1)


class IndentInput(Strict):
    title: str = Field(min_length=1, max_length=300)
    justification: str | None = None
    department_id: str | None = Field(default=None, max_length=36)
    line_id: str = Field(min_length=1, max_length=36)
    items: list[Item] = Field(min_length=1)
    estimated_cost: str = Field(pattern=MONEY)
    needed_by: date | None = None
    document_ids: list[str] = Field(default_factory=list)


class Decision(Strict):
    decision: Literal["approved", "returned", "rejected"]
    note: str | None = None


class TenderInput(Strict):
    title: str = Field(min_length=1, max_length=300)
    indent_ids: list[str] = Field(min_length=1)
    method: Literal["quotation", "tender"]
    invited_vendor_ids: list[str] = Field(default_factory=list)
    category: str | None = Field(default=None, max_length=100)
    closes_at: datetime
    terms: str | None = None
    document_ids: list[str] = Field(default_factory=list)


class QuoteInput(Strict):
    vendor_id: str
    items: list[Item] = Field(default_factory=list)
    total: str = Field(pattern=MONEY)
    delivery_days: int | None = Field(default=None, ge=0)
    valid_until: date | None = None
    document_id: str | None = Field(default=None, max_length=100)


class AwardInput(Strict):
    quote_id: str
    justification: str | None = None


class PurchaseOrderInput(Strict):
    vendor_id: str
    indent_ids: list[str] = Field(min_length=1)
    tender_id: str | None = None
    items: list[Item] = Field(min_length=1)
    delivery_by: date
    delivery_address: str | None = None
    terms: str | None = None


class CancelInput(Strict):
    reason: str = Field(min_length=1)


class ReceiptItem(Strict):
    item_index: int = Field(ge=0)
    received: float = Field(ge=0)
    accepted: float = Field(ge=0)
    rejection_reason: str | None = None


class GoodsReceiptInput(Strict):
    received_on: date
    delivery_note: str | None = None
    items: list[ReceiptItem] = Field(min_length=1)
    document_id: str | None = Field(default=None, max_length=100)


class VendorInvoiceInput(Strict):
    purchase_order_id: str
    invoice_number: str = Field(min_length=1, max_length=60)
    invoice_date: date
    amount: str = Field(pattern=MONEY)
    tax_amount: str | None = Field(default=None, pattern=MONEY)
    document_id: str | None = Field(default=None, max_length=100)


class MarkPaidInput(Strict):
    paid_on: date
    payment_reference: str = Field(min_length=1, max_length=120)
    tds_deducted: str | None = Field(default=None, pattern=MONEY)


def dump(model: BaseModel) -> dict:
    return model.model_dump()
