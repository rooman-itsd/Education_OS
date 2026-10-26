"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

import datetime as dt
from datetime import date
from typing import ClassVar, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Condition = Literal["new", "good", "fair", "poor", "damaged"]
Method = Literal["straight_line", "written_down_value", "none"]
DisposalMethod = Literal["sale", "scrap", "donation", "write_off", "transfer_out", "trade_in"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Patch(Strict):
    """A partial body. Every field is optional, but only the fields in NULLABLE may be set to null explicitly:
    null on anything else would clear a column that cannot be empty, so it is refused (422) instead of a 500."""

    NULLABLE: ClassVar[frozenset[str]] = frozenset()

    @model_validator(mode="after")
    def no_explicit_null_on_required_fields(self):
        bad = [k for k in self.model_fields_set if getattr(self, k) is None and k not in self.NULLABLE]
        if bad:
            raise ValueError(f"{', '.join(sorted(bad))} cannot be null")
        return self


class ReferenceIn(Strict):
    module: str
    entity: str
    id: str


class MoneyIn(Strict):
    amount: str = Field(pattern=r"^-?[0-9]+(\.[0-9]{1,2})?$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class DepreciationIn(Strict):
    method: Method | None = None
    useful_life_months: int | None = Field(default=None, ge=1)
    rate_percent: float | None = Field(default=None, ge=0, le=100)
    residual_percent: float | None = Field(default=None, ge=0, le=100)


class CategoryIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=20)
    description: str | None = None
    depreciation: DepreciationIn | None = None
    verification_interval_months: int | None = Field(default=None, ge=1)


class CategoryPatch(Patch):
    NULLABLE = frozenset({"code", "description", "verification_interval_months"})

    name: str | None = Field(default=None, min_length=1, max_length=120)
    code: str | None = Field(default=None, max_length=20)
    description: str | None = None
    depreciation: DepreciationIn | None = None
    verification_interval_months: int | None = Field(default=None, ge=1)


class AcquisitionIn(Strict):
    date: dt.date | None = None  # the field name shadows the type here
    cost: MoneyIn | None = None
    supplier_name: str | None = None
    invoice_number: str | None = None
    invoice_document_id: str | None = None
    funding_source: str | None = None
    purchase_reference: ReferenceIn | None = None


class AssetIn(Strict):
    tag: str | None = Field(default=None, min_length=1, max_length=60)
    name: str = Field(min_length=1, max_length=200)
    category_id: str
    serial_number: str | None = None
    make: str | None = None
    model: str | None = None
    description: str | None = None
    location: str | None = None
    org_unit_id: str | None = None
    custodian_id: str | None = None
    condition: Condition = "good"
    acquisition: AcquisitionIn | None = None
    in_service_date: date | None = None
    warranty_until: date | None = None
    amc_reference: ReferenceIn | None = None
    inventory_unit_id: str | None = None
    depreciation: DepreciationIn | None = None
    attributes: dict[str, str] | None = None
    photo_document_ids: list[str] | None = None


class AssetPatch(Patch):
    """Any AssetIn field except tag, location, org_unit_id and custodian_id (those change by transfer)."""

    NULLABLE = frozenset(
        {"serial_number", "make", "model", "description", "warranty_until", "amc_reference", "inventory_unit_id"}
    )

    name: str | None = Field(default=None, min_length=1, max_length=200)
    category_id: str | None = None
    serial_number: str | None = None
    make: str | None = None
    model: str | None = None
    description: str | None = None
    acquisition: AcquisitionIn | None = None
    in_service_date: date | None = None
    warranty_until: date | None = None
    amc_reference: ReferenceIn | None = None
    inventory_unit_id: str | None = None
    depreciation: DepreciationIn | None = None
    attributes: dict[str, str] | None = None
    photo_document_ids: list[str] | None = None


class StatusIn(Strict):
    status: Literal["in_service", "in_repair", "idle", "missing"]
    condition: Condition | None = None
    reason: str = Field(min_length=1)


class TransferIn(Strict):
    location: str | None = None
    org_unit_id: str | None = None
    custodian_id: str | None = None
    effective_on: date | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def at_least_one(self):
        if not ({"location", "org_unit_id", "custodian_id"} & self.model_fields_set):
            raise ValueError("give at least one of location, org_unit_id or custodian_id")
        return self


class ScopeIn(Strict):
    category_ids: list[str] | None = None
    org_unit_ids: list[str] | None = None
    location_contains: str | None = None
    only_due: bool = False


class CycleIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    due_on: date
    scope: ScopeIn | None = None
    verifier_user_ids: list[str] = Field(default_factory=list)


class LineIn(Strict):
    asset_id: str | None = None
    tag: str | None = None
    result: Literal["found", "missing", "damaged", "relocated"]
    observed_location: str | None = None
    condition: Condition | None = None
    note: str | None = None
    photo_document_id: str | None = None

    @model_validator(mode="after")
    def identified(self):
        if not (self.asset_id or self.tag):
            raise ValueError("give asset_id or tag")
        return self


class CloseIn(Strict):
    close_with_pending: bool = False
    note: str | None = None


class RunIn(Strict):
    period_end: date
    category_ids: list[str] | None = None


class DisposalIn(Strict):
    asset_id: str
    method: DisposalMethod
    reason: str = Field(min_length=1)
    expected_proceeds: MoneyIn | None = None


class DecisionIn(Strict):
    note: str | None = None


class RejectIn(Strict):
    reason: str = Field(min_length=1)


class CompletionIn(Strict):
    disposed_on: date
    proceeds: MoneyIn | None = None
    recipient: str | None = None
    certificate_document_id: str | None = None
    note: str | None = None


def _clean(value):
    """Nested objects keep only the values the caller gave, so a category default is not overwritten by null."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items() if v is not None}
    return value


def dump(model: BaseModel | None, *, partial: bool = False) -> dict:
    """Plain dict for the service. Partial bodies keep only the fields the caller sent (and explicit nulls only on
    NULLABLE fields); full bodies drop nulls."""
    if model is None:
        return {}
    data = model.model_dump(exclude_unset=partial)
    for key in ("depreciation", "acquisition", "scope"):
        if isinstance(data.get(key), dict):
            data[key] = _clean(data[key])
    if partial:
        nullable = getattr(model, "NULLABLE", frozenset())
        data = {k: v for k, v in data.items() if v is not None or k in nullable}
    else:
        data = {k: v for k, v in data.items() if v is not None}
    return data
