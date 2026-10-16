"""Request bodies, mirroring contracts/openapi.yaml components. `from` and `to` are Python keywords, so those
fields use an alias and are dumped by alias."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# The contract types every id as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def dump(body: BaseModel) -> dict:
    return body.model_dump(by_alias=True)


class HostelIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    occupancy_type: str = Field(min_length=1, max_length=60)
    warden_ids: list[Uuid] | None = None
    active: bool = True


class HostelPatch(Strict):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    occupancy_type: str | None = Field(default=None, min_length=1, max_length=60)
    warden_ids: list[Uuid] | None = None
    active: bool | None = None


class RoomIn(Strict):
    number: str = Field(min_length=1, max_length=40)
    floor: str | None = Field(default=None, max_length=40)
    room_type: str = Field(min_length=1, max_length=60)
    capacity: int = Field(ge=1)


class RoomUpdate(Strict):
    room_type: str | None = Field(default=None, min_length=1, max_length=60)
    capacity: int | None = Field(default=None, ge=1)
    status: Literal["open", "closed"] | None = None
    reason: str | None = None


class RoomRequestIn(Strict):
    academic_year: str = Field(min_length=1, max_length=20)
    preferred_hostel_id: Uuid | None = None
    preferred_room_type: str | None = Field(default=None, max_length=60)
    notes: str | None = None


class AllocationIn(Strict):
    person_id: Uuid
    room_id: Uuid
    bed: str = Field(min_length=1, max_length=20)
    academic_year: str = Field(min_length=1, max_length=20)
    from_: date = Field(alias="from")
    to: date


class ConfirmIn(Strict):
    room_id: Uuid
    bed: str = Field(min_length=1, max_length=20)
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None


class CheckOutIn(Strict):
    condition_notes: str | None = None


class ReasonIn(Strict):
    reason: str = Field(min_length=3)


class MessMenuIn(Strict):
    hostel_id: Uuid
    menu_date: date = Field(alias="date")
    meal: str = Field(min_length=1, max_length=60)
    items: list[str]


class LeaveIn(Strict):
    from_: datetime = Field(alias="from")
    to: datetime
    destination: str = Field(min_length=1, max_length=300)
    reason: str = Field(min_length=1)
    contact_phone: str | None = Field(default=None, max_length=40)


class DecisionIn(Strict):
    decision: Literal["approved", "rejected"]
    reason: str | None = None


class VisitIn(Strict):
    person_id: Uuid
    visitor_name: str = Field(min_length=1, max_length=200)
    relation: str | None = Field(default=None, max_length=100)
    id_document_note: str | None = Field(default=None, max_length=100)


class IncidentIn(Strict):
    person_id: Uuid
    occurred_at: datetime
    category: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1)
    action_taken: str | None = None


class IncidentPatch(Strict):
    action_taken: str | None = None
    status: Literal["open", "closed"] | None = None


class NoticeIn(Strict):
    hostel_id: Uuid | None = None
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1)
    expires_at: datetime | None = None
