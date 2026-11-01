"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field
is a 422, never silently ignored."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
CoverageType = Literal["comprehensive", "non_comprehensive"]
EngagementKind = Literal["breakdown_call", "preventive_visit"]
# A plain shape check for VendorContact.email (format: email), without an extra dependency.
Email = Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
# Upper bounds the contract leaves open, set to what the columns hold, so a value too big is a 422, never a database
# error or an overflow when the response and resolution due times are worked out.
MAX_HOURS = 8760  # a year
MAX_VISITS_PER_YEAR = 366


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Fields the contract lets a PATCH set to null (`oneOf: [..., {type: "null"}]` or `type: [..., "null"]`).
NULLABLE_ON_PATCH = frozenset({"purchase_order_reference", "covered_item_id"})


def as_dict(body: BaseModel, *, partial: bool) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH): only the fields the caller
    sent, so only those change; a null is kept only where the contract allows one, so it never clears a required
    value."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None or k in NULLABLE_ON_PATCH}
    return data


class Money(Strict):
    amount: str = Field(pattern=r"^[0-9]{1,12}(\.[0-9]{1,2})?$")  # Numeric(14, 2)
    # The contract lists currency as required and also says it defaults to AMC_VENDOR_SUPPORT_DEFAULT_CURRENCY; a
    # missing currency gets that default.
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")


class Reference(Strict):
    module: str = Field(min_length=1, max_length=60)
    entity: str = Field(min_length=1, max_length=60)
    id: str = Field(min_length=1, max_length=100)


class VendorContact(Strict):
    name: str = Field(min_length=1)
    phone: str | None = None
    email: Email | None = None


class ContractInput(Strict):
    vendor_id: Uuid
    title: str = Field(min_length=3, max_length=200)
    coverage_type: CoverageType
    scope: str | None = None
    start_date: date
    end_date: date
    value: Money | None = None
    purchase_order_reference: Reference | None = None
    response_hours: int | None = Field(default=None, ge=1, le=MAX_HOURS)
    resolution_hours: int | None = Field(default=None, ge=1, le=MAX_HOURS)
    preventive_visits_per_year: int | None = Field(default=None, ge=0, le=MAX_VISITS_PER_YEAR)
    vendor_contacts: list[VendorContact] | None = None
    owner_id: Uuid | None = None
    renewal_notice_days: int = Field(default=60, ge=0, le=366)


class ContractUpdateInput(Strict):
    vendor_id: Uuid | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    coverage_type: CoverageType | None = None
    scope: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    value: Money | None = None
    purchase_order_reference: Reference | None = None
    response_hours: int | None = Field(default=None, ge=1, le=MAX_HOURS)
    resolution_hours: int | None = Field(default=None, ge=1, le=MAX_HOURS)
    preventive_visits_per_year: int | None = Field(default=None, ge=0, le=MAX_VISITS_PER_YEAR)
    vendor_contacts: list[VendorContact] | None = None
    owner_id: Uuid | None = None
    renewal_notice_days: int | None = Field(default=None, ge=0, le=366)


class TerminateInput(Strict):
    reason: str = Field(min_length=3)
    effective_date: date


class RenewInput(Strict):
    start_date: date | None = None
    end_date: date
    value: Money | None = None
    purchase_order_reference: Reference | None = None


class CoveredItemInput(Strict):
    description: str = Field(min_length=2, max_length=200)
    reference: Reference | None = None


class EngagementInput(Strict):
    contract_id: Uuid
    kind: EngagementKind
    description: str = Field(min_length=3)
    covered_item_id: Uuid | None = None
    references: list[Reference] | None = None
    vendor_call_reference: str | None = Field(default=None, max_length=100)
    reported_at: datetime | None = None


class EngagementUpdateInput(Strict):
    description: str | None = Field(default=None, min_length=3)
    covered_item_id: Uuid | None = None
    references: list[Reference] | None = None
    vendor_call_reference: str | None = Field(default=None, max_length=100)
    reported_at: datetime | None = None


class EngagementStatusInput(Strict):
    status: Literal["in_progress", "resolved", "closed", "cancelled"]
    at: datetime | None = None
    resolution_note: str | None = Field(default=None, min_length=3)
    note: str | None = Field(default=None, min_length=3)
