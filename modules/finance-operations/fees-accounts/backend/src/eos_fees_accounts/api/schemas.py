"""Request bodies of contracts/openapi.yaml. Strict: unknown fields are refused. Money stays a decimal string here;
the domain parses it exactly."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

MONEY = r"^-?[0-9]+(\.[0-9]{1,2})?$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class FeeHeadInput(Strict):
    code: str = Field(pattern=r"^[A-Z0-9_]{2,20}$")
    name: str = Field(min_length=1, max_length=120)
    category: Literal[
        "admission", "tuition", "examination", "hostel", "transport", "library", "deposit", "fine", "other"
    ] = "other"
    refundable: bool = False
    active: bool = True


class StructureItem(Strict):
    fee_head_id: str
    amount: str = Field(pattern=MONEY)


class StructureInstalment(Strict):
    label: str = Field(min_length=1, max_length=100)
    percent: float = Field(ge=0, le=100)
    due_date: date


class LateFeeRule(Strict):
    kind: Literal["flat", "per_day"]
    amount: str = Field(pattern=MONEY)
    grace_days: int = Field(default=0, ge=0)
    cap: str | None = Field(default=None, pattern=MONEY)


class FeeStructureInput(Strict):
    name: str = Field(min_length=1, max_length=200)
    academic_year: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$")
    programme_id: str | None = None
    applies_to: Literal["applicant", "student"] = "student"
    category: str | None = None
    room_type: str | None = None
    route_id: str | None = None
    items: list[StructureItem] = Field(min_length=1)
    instalments: list[StructureInstalment] = Field(min_length=1)
    allow_part_payment: bool = False
    late_fee: LateFeeRule | None = None


class InvoiceLineInput(Strict):
    fee_head_id: str
    description: str | None = Field(default=None, max_length=300)
    amount: str = Field(pattern=MONEY)


class InvoiceSource(Strict):
    module: str | None = Field(default=None, max_length=60)
    reference: str | None = Field(default=None, max_length=100)


class InvoiceInput(Strict):
    person_id: str
    fee_structure_id: str | None = None
    instalment: int | None = Field(default=None, ge=1)
    lines: list[InvoiceLineInput] | None = None
    due_date: date | None = None
    source: InvoiceSource | None = None


class BulkInvoiceInput(Strict):
    fee_structure_id: str
    instalment: int = Field(ge=1)
    person_ids: list[str] = Field(min_length=1, max_length=5000)


class Reason(Strict):
    reason: str = Field(min_length=1)


class PayInput(Strict):
    amount: str | None = Field(default=None, pattern=MONEY)
    return_url: str | None = None


class OfflinePaymentInput(Strict):
    amount: str = Field(pattern=MONEY)
    mode: Literal["cash", "cheque", "demand_draft", "bank_transfer"]
    paid_on: date
    instrument_number: str | None = Field(default=None, max_length=60)
    bank_name: str | None = Field(default=None, max_length=120)
    note: str | None = None


class RefundInput(Strict):
    amount: str = Field(pattern=MONEY)
    reason: str = Field(min_length=1)
    mode: Literal["original", "cash", "cheque", "bank_transfer"] = "original"


class ConcessionInput(Strict):
    invoice_id: str
    kind: Literal["scholarship", "waiver", "staff_ward", "sibling", "other"]
    amount: str | None = Field(default=None, pattern=MONEY)
    percent: float | None = Field(default=None, ge=0, le=100)
    reason: str = Field(min_length=1)
    document_id: str | None = None


class ConcessionDecision(Strict):
    decision: Literal["approved", "rejected"]
    note: str | None = None


class CollectionTargetInput(Strict):
    period: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$")
    amount: str = Field(pattern=MONEY)
    fee_head_id: str | None = None


class TargetsInput(Strict):
    academic_year: str = Field(pattern=r"^[0-9]{4}-[0-9]{2}$")
    targets: list[CollectionTargetInput]


class SettingsInput(Strict):
    invoice_library_fines: bool = False
    invoice_staff_transport: bool = False


def dump(model: BaseModel) -> dict:
    return model.model_dump(mode="python")
