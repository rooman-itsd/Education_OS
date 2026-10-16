"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Condition = Literal["new", "good", "fair", "poor", "damaged"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class LoanRulesIn(Strict):
    requires_approval: bool | None = None
    max_loan_days: int | None = Field(default=None, ge=1)
    max_quantity_per_loan: int | None = Field(default=None, ge=1)
    borrower_role_ids: list[str] | None = None


class CategoryIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    approver_user_ids: list[str] | None = None
    default_loan_rules: LoanRulesIn | None = None


class CategoryPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    approver_user_ids: list[str] | None = None
    default_loan_rules: LoanRulesIn | None = None


class LocationIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    address: str | None = None
    keeper_user_ids: list[str] | None = None
    active: bool = True


class LocationPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    address: str | None = None
    keeper_user_ids: list[str] | None = None
    active: bool | None = None


class ItemIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=60)
    category_id: str
    tracking: Literal["individual", "quantity"]
    unit_of_measure: str = "piece"
    loanable: bool = True
    consumable: bool = False
    reorder_level: float | None = Field(default=None, ge=0)
    reorder_quantity: float | None = Field(default=None, ge=0)
    description: str | None = None
    attributes: dict[str, str] | None = None
    image_document_id: str | None = None
    loan_rules: LoanRulesIn | None = None
    active: bool = True


class ItemPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    code: str | None = Field(default=None, max_length=60)
    category_id: str | None = None
    tracking: Literal["individual", "quantity"] | None = None
    unit_of_measure: str | None = None
    loanable: bool | None = None
    consumable: bool | None = None
    reorder_level: float | None = Field(default=None, ge=0)
    reorder_quantity: float | None = Field(default=None, ge=0)
    description: str | None = None
    attributes: dict[str, str] | None = None
    image_document_id: str | None = None
    loan_rules: LoanRulesIn | None = None
    active: bool | None = None


class UnitIn(Strict):
    tag: str = Field(min_length=1, max_length=60)
    serial_number: str | None = None
    location_id: str | None = None
    condition: Condition = "good"
    asset_id: str | None = None
    notes: str | None = None


class UnitPatch(Strict):
    tag: str | None = Field(default=None, min_length=1, max_length=60)
    serial_number: str | None = None
    location_id: str | None = None
    condition: Condition | None = None
    asset_id: str | None = None
    notes: str | None = None


class UnitStatusIn(Strict):
    status: Literal["available", "in_repair", "missing", "retired"] | None = None
    condition: Condition | None = None
    reason: str = Field(min_length=1)


class ReferenceIn(Strict):
    module: str
    entity: str
    id: str


class MovementIn(Strict):
    kind: Literal["receipt", "issue", "transfer", "adjustment", "write_off"]
    item_id: str
    quantity: float
    unit_ids: list[str] | None = None
    from_location_id: str | None = None
    to_location_id: str | None = None
    issued_to: str | None = None
    reason: str | None = None
    reference: ReferenceIn | None = None


class LoanLineIn(Strict):
    item_id: str
    quantity: float = Field(default=1, ge=1)
    unit_id: str | None = None


class LoanIn(Strict):
    lines: list[LoanLineIn] = Field(min_length=1)
    due_at: datetime
    purpose: str | None = Field(default=None, max_length=300)
    borrower_id: str | None = None
    reference: ReferenceIn | None = None


class HandOutLineIn(Strict):
    line_id: str
    unit_id: str | None = None
    from_location_id: str | None = None
    condition_out: Condition | None = None


class HandOutIn(Strict):
    lines: list[HandOutLineIn]


class ReturnLineIn(Strict):
    line_id: str
    condition_in: Condition
    to_location_id: str | None = None
    damage_note: str | None = None


class ReturnIn(Strict):
    lines: list[ReturnLineIn] = Field(min_length=1)


class ExtendIn(Strict):
    due_at: datetime
    reason: str | None = None


class MarkLostIn(Strict):
    line_ids: list[str] = Field(min_length=1)
    reason: str = Field(min_length=1)


class NoteIn(Strict):
    note: str | None = None


class ReasonIn(Strict):
    reason: str | None = None


class RequiredReasonIn(Strict):
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def not_blank(self):
        if not self.reason.strip():
            raise ValueError("reason must not be blank")
        return self


def dump(model: BaseModel | None, *, partial: bool = False) -> dict:
    """Plain dict for the service. Partial bodies keep only the fields the caller sent."""
    if model is None:
        return {}
    data = model.model_dump(exclude_unset=partial)
    for key in ("loan_rules", "default_loan_rules"):
        if isinstance(data.get(key), dict):
            data[key] = {k: v for k, v in data[key].items() if v is not None}
    if not partial:
        data = {k: v for k, v in data.items() if v is not None}
    return data
