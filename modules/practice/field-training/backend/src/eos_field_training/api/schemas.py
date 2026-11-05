"""Request bodies, mirroring contracts/openapi.yaml components. Optional fields left out of a body keep their stored
value, so handlers dump with exclude_unset. Every string and number is bounded so nothing oversized reaches the
database: a bad value is a 422, never a 500."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

# The contract types every id as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
# Hours in steps of 0.25 (contract component Hours). A requirement is bounded well above any real one.
RequiredHours = Annotated[float, Field(ge=0, le=10000, multiple_of=0.25)]
EntryHours = Annotated[float, Field(gt=0, le=24, multiple_of=0.25)]
SupervisorIds = Annotated[list[Uuid], Field(max_length=50)]


def _in_range(value: date) -> date:
    """Dates near year 1 or 9999 overflow the 14-day window and the due-date arithmetic; nothing here is that far."""
    if not 1900 <= value.year <= 9998:
        raise ValueError("must be between the years 1900 and 9998")
    return value


Day = Annotated[date, AfterValidator(_in_range)]


def has_nul(value) -> bool:
    """A NUL character anywhere in a string, list or dict. Postgres text cannot hold one (a 500 otherwise)."""
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, list | tuple):
        return any(has_nul(v) for v in value)
    if isinstance(value, dict):
        return any(has_nul(k) or has_nul(v) for k, v in value.items())
    return False


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    @field_validator("*")
    @classmethod
    def _no_nul(cls, value):
        if has_nul(value):
            raise ValueError("must not contain NUL characters")
        return value


def dump(body: BaseModel) -> dict:
    return body.model_dump(exclude_unset=True)


class ReasonIn(Strict):
    reason: str = Field(min_length=3, max_length=2000)


class SiteIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    kind: str | None = Field(default=None, max_length=100)
    address: str | None = Field(default=None, max_length=500)
    contact_name: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=254, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    supervisor_ids: SupervisorIds | None = None
    active: bool | None = None


class OpeningIn(Strict):
    site_id: Uuid
    title: str = Field(min_length=1, max_length=200)
    discipline: str | None = Field(default=None, max_length=100)
    starts_on: Day
    ends_on: Day
    seats: int = Field(ge=1, le=10000)
    required_hours: RequiredHours | None = None
    allow_applications: bool | None = None
    eligibility: str | None = Field(default=None, max_length=2000)
    supervisor_ids: SupervisorIds | None = None


class ApplyIn(Strict):
    statement: str | None = Field(default=None, max_length=2000)


class AssignIn(Strict):
    opening_id: Uuid
    trainee_id: Uuid
    supervisor_id: Uuid | None = None
    starts_on: Day | None = None
    ends_on: Day | None = None


class PlacementPatchIn(Strict):
    supervisor_id: Uuid | None = None
    starts_on: Day | None = None
    ends_on: Day | None = None


class DecisionIn(Strict):
    decision: Literal["approved", "rejected"]
    supervisor_id: Uuid | None = None
    reason: str | None = Field(default=None, max_length=2000)


class CompleteIn(Strict):
    override: bool = False
    reason: str | None = Field(default=None, max_length=2000)


class LogEntryIn(Strict):
    date: Day
    hours: EntryHours
    activities: str = Field(min_length=1, max_length=4000)
    reflection: str | None = Field(default=None, max_length=4000)


class AssessmentIn(Strict):
    stage: Literal["mid", "final"]
    outcome: str = Field(min_length=1, max_length=200)
    score: float | None = Field(default=None, ge=0, le=100)
    comments: str | None = Field(default=None, max_length=4000)
