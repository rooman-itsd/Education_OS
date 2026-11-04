"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field
is a 422, never silently ignored. Bounds the contract leaves open are set to what the columns and the business-time
arithmetic hold, so a value too big is a 422, never a database error or an overflow."""

from __future__ import annotations

import datetime as dt
import re
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from ..domain.business_time import MAX_TARGET_MINUTES, MAX_ZONE_NAME
from ..infrastructure.config import LEVELS_CAP

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row; kept in lower case,
# as helpdesk and identity give them out.
Uuid = Annotated[str, Field(pattern=UUID_PATTERN), AfterValidator(str.lower)]
Priority = Literal["low", "medium", "high", "urgent"]
HoldReason = Literal["waiting_requester", "waiting_third_party", "waiting_internal"]
Minutes = Annotated[int, Field(ge=1, le=MAX_TARGET_MINUTES)]
Name = Annotated[str, Field(min_length=1, max_length=80)]  # String(80)
TimeZone = Annotated[str, Field(min_length=1, max_length=MAX_ZONE_NAME)]  # String(64)

MAX_WORKING_INTERVALS = 70  # ten a day
MAX_HOLIDAYS = 1000
MAX_PEOPLE_PER_LEVEL = 50


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Fields the contract lets a PATCH set to null (`type: [..., "null"]`).
NULLABLE_ON_PATCH = frozenset({"category_id"})


def as_dict(body: BaseModel, *, partial: bool) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH): only the fields the caller
    sent, so only those change; a null is kept only where the contract allows one, so it never clears a required
    value."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None or k in NULLABLE_ON_PATCH}
    return data


class WorkingInterval(Strict):
    weekday: int = Field(ge=1, le=7)
    start: str = Field(pattern=r"^([01][0-9]|2[0-3]):[0-5][0-9]$")
    end: str = Field(pattern=r"^([01][0-9]|2[0-4]):[0-5][0-9]$")


class Holiday(Strict):
    date: dt.date
    name: Name


class CalendarInput(Strict):
    name: Name
    time_zone: TimeZone
    always_open: bool = False
    working_hours: list[WorkingInterval] = Field(default_factory=list, max_length=MAX_WORKING_INTERVALS)
    holidays: list[Holiday] = Field(default_factory=list, max_length=MAX_HOLIDAYS)
    active: bool = True


class CalendarUpdateInput(Strict):
    name: Name | None = None
    time_zone: TimeZone | None = None
    always_open: bool | None = None
    working_hours: list[WorkingInterval] | None = Field(default=None, max_length=MAX_WORKING_INTERVALS)
    holidays: list[Holiday] | None = Field(default=None, max_length=MAX_HOLIDAYS)
    active: bool | None = None


class EscalationLevel(Strict):
    level: int = Field(ge=1, le=LEVELS_CAP)
    after_breach_minutes: int = Field(ge=0, le=MAX_TARGET_MINUTES)
    notify_assignee: bool = True
    notify_person_ids: list[Uuid] = Field(default_factory=list, max_length=MAX_PEOPLE_PER_LEVEL)


class PolicyInput(Strict):
    name: Name
    priority: Priority
    category_id: Uuid | None = None
    calendar_id: Uuid
    response_target_minutes: Minutes
    resolution_target_minutes: Minutes
    warning_percent: int | None = Field(default=None, ge=1, le=99)
    pause_on_hold_reasons: list[HoldReason] = Field(
        default_factory=lambda: ["waiting_requester", "waiting_third_party"], max_length=3
    )
    escalation_levels: list[EscalationLevel] = Field(default_factory=list, max_length=LEVELS_CAP)
    active: bool = True


class PolicyUpdateInput(Strict):
    name: Name | None = None
    priority: Priority | None = None
    category_id: Uuid | None = None
    calendar_id: Uuid | None = None
    response_target_minutes: Minutes | None = None
    resolution_target_minutes: Minutes | None = None
    warning_percent: int | None = Field(default=None, ge=1, le=99)
    pause_on_hold_reasons: list[HoldReason] | None = Field(default=None, max_length=3)
    escalation_levels: list[EscalationLevel] | None = Field(default=None, max_length=LEVELS_CAP)
    active: bool | None = None


UUID_RE = re.compile(UUID_PATTERN)
