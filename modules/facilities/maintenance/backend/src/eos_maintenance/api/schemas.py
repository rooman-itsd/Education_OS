"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

Priority = Literal["low", "medium", "high", "urgent"]
TargetKind = Literal["asset", "resource", "unit", "location"]
HoldReason = Literal["waiting_parts", "waiting_vendor", "waiting_access", "other"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ReferenceIn(Strict):
    module: str
    entity: str
    id: str


class TargetIn(Strict):
    kind: TargetKind
    id: str | None = None
    label: str = Field(min_length=1, max_length=300)


class MoneyIn(Strict):
    amount: str = Field(pattern=r"^[0-9]+(\.[0-9]{1,2})?$")
    currency: str = Field(pattern=r"^[A-Z]{3}$")


class SlaOverrideIn(Strict):
    response_hours: dict[str, int] | None = None
    resolution_hours: dict[str, int] | None = None

    @model_validator(mode="after")
    def positive(self):
        for hours in (self.response_hours or {}, self.resolution_hours or {}):
            if any(v < 1 for v in hours.values()):
                raise ValueError("SLA hours must be at least 1")
        return self


class CategoryIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    default_priority: Priority = "medium"
    default_assignee_ids: list[str] = Field(default_factory=list)
    sla_override: SlaOverrideIn | None = None
    active: bool = True


class CategoryPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    default_priority: Priority | None = None
    default_assignee_ids: list[str] | None = None
    sla_override: SlaOverrideIn | None = None
    active: bool | None = None


class TicketIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: str
    kind: Literal["corrective", "inspection"] = "corrective"
    target: TargetIn
    priority: Priority | None = None
    blocks_use: bool = False
    photo_document_ids: list[str] | None = None
    source: ReferenceIn | None = None


class TicketPatch(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category_id: str | None = None
    priority: Priority | None = None
    target: TargetIn | None = None
    blocks_use: bool | None = None


class VendorIn(Strict):
    name: str = Field(min_length=1)
    contact: str | None = None
    job_number: str | None = None
    amc_reference: ReferenceIn | None = None


class AssignmentIn(Strict):
    assignee_id: str | None = None
    vendor: VendorIn | None = None
    note: str | None = None

    @model_validator(mode="after")
    def exactly_one(self):
        if bool(self.assignee_id) == bool(self.vendor):
            raise ValueError("give exactly one of assignee_id or vendor")
        return self


class HoldIn(Strict):
    reason: HoldReason
    note: str | None = None


class ChecklistResultIn(Strict):
    step: str
    done: bool
    note: str | None = None


class ResolutionIn(Strict):
    note: str = Field(min_length=1)
    root_cause: str | None = None
    checklist: list[ChecklistResultIn] | None = None
    target_usable: bool = True


class CloseIn(Strict):
    feedback: str | None = None
    rating: int | None = Field(default=None, ge=1, le=5)


class ReopenIn(Strict):
    reason: str = Field(min_length=1)


class CancelIn(Strict):
    reason: str = Field(min_length=1)
    duplicate_of: str | None = None


class WorkEntryIn(Strict):
    kind: Literal["note", "time", "part", "cost"]
    note: str | None = None
    minutes: int | None = Field(default=None, ge=1)
    item_id: str | None = None
    item_name: str | None = None
    quantity: float | None = Field(default=None, ge=0)
    cost: MoneyIn | None = None
    document_id: str | None = None


class ScheduleIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = None
    category_id: str
    target: TargetIn
    kind: Literal["preventive", "inspection"] = "preventive"
    every: int = Field(ge=1)
    unit: Literal["days", "weeks", "months"]
    next_due_on: date
    lead_days: int | None = Field(default=None, ge=0)
    priority: Priority | None = None
    default_assignee_id: str | None = None
    checklist: list[str] = Field(default_factory=list)
    active: bool = True


class SchedulePatch(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    category_id: str | None = None
    target: TargetIn | None = None
    kind: Literal["preventive", "inspection"] | None = None
    every: int | None = Field(default=None, ge=1)
    unit: Literal["days", "weeks", "months"] | None = None
    next_due_on: date | None = None
    lead_days: int | None = Field(default=None, ge=0)
    priority: Priority | None = None
    default_assignee_id: str | None = None
    checklist: list[str] | None = None
    active: bool | None = None


def dump(model: BaseModel | None, *, partial: bool = False) -> dict:
    """Plain dict for the service. Partial bodies keep only the fields the caller sent; full bodies drop nulls."""
    if model is None:
        return {}
    data = model.model_dump(exclude_unset=partial)
    if isinstance(data.get("sla_override"), dict):
        data["sla_override"] = {k: v for k, v in data["sla_override"].items() if v is not None}
    if not partial:
        data = {k: v for k, v in data.items() if v is not None}
    return data
