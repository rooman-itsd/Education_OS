"""Request bodies, mirroring contracts/openapi.yaml components. Optional fields left out of a PATCH body keep
their stored value, so handlers dump with exclude_unset."""

from __future__ import annotations

from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

# The contract types every id as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
Latitude = Annotated[float, Field(ge=-90, le=90)]
Longitude = Annotated[float, Field(ge=-180, le=180)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


def dump(body: BaseModel) -> dict:
    return body.model_dump(exclude_unset=True)


class StopIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    latitude: Latitude | None = None
    longitude: Longitude | None = None


class RouteStopIn(Strict):
    stop_id: Uuid
    sequence: int = Field(ge=1)
    scheduled_time: str | None = Field(default=None, pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    stop_name: str | None = None  # readOnly in the contract; accepted and ignored so a GET body can be sent back


class RouteIn(Strict):
    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    direction: str | None = Field(default=None, max_length=100)
    stops: list[RouteStopIn] = Field(min_length=2)
    active: bool | None = None


class AssignmentIn(Strict):
    vehicle_id: Uuid
    driver_id: Uuid


class VehicleIn(Strict):
    registration_no: str = Field(min_length=1, max_length=40)
    type: str | None = Field(default=None, max_length=60)
    capacity: int = Field(ge=1)
    insurance_expires_on: date | None = None
    fitness_expires_on: date | None = None
    permit_expires_on: date | None = None
    active: bool | None = None


class DriverIn(Strict):
    person_id: Uuid | None = None
    name: str = Field(min_length=1, max_length=200)
    licence_no: str = Field(min_length=1, max_length=60)
    licence_expires_on: date
    phone: str | None = Field(default=None, max_length=40)
    active: bool | None = None


class PassRequestIn(Strict):
    route_id: Uuid
    stop_id: Uuid
    valid_from: date
    valid_to: date


class PassIssueIn(PassRequestIn):
    person_id: Uuid
    rider_type: Literal["student", "staff"] = "student"
    override_capacity: bool = False
    reason: str | None = None


class DecisionIn(Strict):
    decision: Literal["issued", "rejected"]
    reason: str | None = None
    override_capacity: bool = False


class ReasonIn(Strict):
    reason: str = Field(min_length=3)


class TripIn(Strict):
    route_id: Uuid


class PositionIn(Strict):
    recorded_at: datetime
    latitude: Latitude
    longitude: Longitude
    speed_kmh: float | None = Field(default=None, ge=0)


class DelayIn(Strict):
    delay_minutes: int = Field(ge=0)
    note: str | None = None


class NoticeIn(Strict):
    route_id: Uuid | None = None
    kind: Literal["delay", "cancellation", "route-change", "general"]
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1)
    expires_at: datetime | None = None
