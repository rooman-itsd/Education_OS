"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

HHMM = r"^([01][0-9]|2[0-3]):[0-5][0-9]$"
HHMM_OR_24 = r"^(([01][0-9]|2[0-3]):[0-5][0-9]|24:00)$"


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BookingRulesIn(Strict):
    requires_approval: bool | None = None
    check_in_required: bool | None = None
    min_duration_minutes: int | None = Field(default=None, ge=1)
    max_duration_minutes: int | None = Field(default=None, ge=1)
    slot_minutes: int | None = Field(default=None, ge=5)
    max_days_ahead: int | None = Field(default=None, ge=0)
    buffer_minutes: int | None = Field(default=None, ge=0)
    max_concurrent_bookings: int | None = Field(default=None, ge=1)
    bookable_role_ids: list[str] | None = None


class ResourceTypeIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    description: str | None = None
    colour: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    default_rules: BookingRulesIn | None = None


class ResourceTypePatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = None
    colour: str | None = Field(default=None, pattern=r"^#[0-9a-fA-F]{6}$")
    default_rules: BookingRulesIn | None = None


class ResourceIn(Strict):
    name: str = Field(min_length=1, max_length=120)
    type_id: str
    code: str | None = Field(default=None, max_length=40)
    location: str | None = None
    capacity: int | None = Field(default=None, ge=1)
    description: str | None = None
    attributes: dict[str, str] | None = None
    image_document_id: str | None = None
    approver_user_ids: list[str] | None = None
    rules: BookingRulesIn | None = None


class ResourcePatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    type_id: str | None = None
    code: str | None = Field(default=None, max_length=40)
    location: str | None = None
    capacity: int | None = Field(default=None, ge=1)
    description: str | None = None
    attributes: dict[str, str] | None = None
    image_document_id: str | None = None
    approver_user_ids: list[str] | None = None
    rules: BookingRulesIn | None = None


class StatusIn(Strict):
    status: Literal["active", "inactive", "under_maintenance"]
    reason: str | None = None


class OpeningHoursIn(Strict):
    weekday: int = Field(ge=1, le=7)
    opens: str = Field(pattern=HHMM)
    closes: str = Field(pattern=HHMM_OR_24)

    @model_validator(mode="after")
    def closes_after_opens(self):
        if self.closes <= self.opens:
            raise ValueError("closes must be after opens")
        return self


class BlackoutIn(Strict):
    start_at: datetime
    end_at: datetime
    reason: str = Field(min_length=1, max_length=300)


class SourceIn(Strict):
    module: str
    entity: str
    id: str


class RecurrenceIn(Strict):
    frequency: Literal["daily", "weekly"]
    interval: int = Field(default=1, ge=1)
    weekdays: list[int] | None = None
    until: date | None = None
    count: int | None = Field(default=None, ge=1)

    @field_validator("weekdays")
    @classmethod
    def iso_weekdays(cls, value):
        if value and any(d < 1 or d > 7 for d in value):
            raise ValueError("weekdays are 1 (Monday) to 7")
        return value

    @model_validator(mode="after")
    def until_or_count(self):
        if (self.until is None) == (self.count is None):
            raise ValueError("give exactly one of until or count")
        return self


class BookingIn(Strict):
    resource_id: str
    start_at: datetime
    end_at: datetime
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    party_size: int = Field(default=1, ge=1)
    booked_for: str | None = None
    source: SourceIn | None = None
    recurrence: RecurrenceIn | None = None
    skip_conflicts: bool = False


class BookingPatch(Strict):
    resource_id: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    title: str | None = Field(default=None, max_length=200)
    notes: str | None = None
    party_size: int | None = Field(default=None, ge=1)


class NoteIn(Strict):
    note: str | None = None


class ReasonIn(Strict):
    reason: str | None = None


class RequiredReasonIn(Strict):
    reason: str = Field(min_length=1)


def dump(model: BaseModel | None, *, partial: bool = False) -> dict:
    """Plain dict for the service. Partial bodies keep only the fields the caller sent."""
    if model is None:
        return {}
    data = model.model_dump(exclude_unset=partial)
    for key in ("rules", "default_rules"):
        if isinstance(data.get(key), dict):
            data[key] = {k: v for k, v in data[key].items() if v is not None}
    if not partial:
        data = {k: v for k, v in data.items() if v is not None}
    return data
