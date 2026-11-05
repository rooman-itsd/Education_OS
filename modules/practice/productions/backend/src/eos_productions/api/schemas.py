"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator

from ..application.service import NOT_NULLABLE

Kind = Literal["performance", "exhibition", "recital", "screening", "hackathon", "competition", "conference", "other"]
RoleKind = Literal["cast", "crew", "mentor"]
#: Stripped *before* the length check, so "   " is a 422 rather than a stored empty string (review of #454).
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
RoleName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]

#: A production is never dated outside these years. Without a bound, 0001-01-01 or 9999-12-31 reached
#: `timedelta` arithmetic and `astimezone` and raised OverflowError (a 500). Checked on the year as written, so
#: the check itself cannot overflow on an offset. (Review of #454.)
MIN_YEAR, MAX_YEAR = 2000, 2100


def _in_range(value: datetime) -> datetime:
    if not MIN_YEAR <= value.year <= MAX_YEAR:
        raise ValueError(f"must be between the years {MIN_YEAR} and {MAX_YEAR}")
    return value


Moment = Annotated[datetime, AfterValidator(_in_range)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductionIn(Strict):
    title: Title
    kind: Kind
    department: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=2000)
    venue: str | None = Field(default=None, max_length=200)
    resource_id: str | None = Field(default=None, max_length=36)
    lead_user_id: str | None = None
    starts_at: Moment | None = None
    ends_at: Moment | None = None
    call_time: Moment | None = None
    client_token: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def dates_come_in_pairs(self):
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("give both starts_at and ends_at, or neither")
        return self


class ProductionPatch(Strict):
    title: Title | None = None
    kind: Kind | None = None
    department: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=2000)
    venue: str | None = Field(default=None, max_length=200)
    resource_id: str | None = Field(default=None, max_length=36)
    lead_user_id: str | None = None

    @model_validator(mode="before")
    @classmethod
    def refuse_explicit_null(cls, data):
        """`{"kind": null}` used to reach the column and raise IntegrityError (a 500); `{"title": null}` was
        silently ignored. Both are a caller mistake, so both are refused here, before the service sees them.
        Omitting a field still means "leave it alone" — only an explicit null is an error. (Review of #454.)"""
        if isinstance(data, dict):
            nulls = sorted(k for k in NOT_NULLABLE if k in data and data[k] is None)
            if nulls:
                raise ValueError(f"{', '.join(nulls)}: cannot be cleared; omit the field to leave it unchanged")
        return data


class ScheduleIn(Strict):
    starts_at: Moment
    ends_at: Moment
    call_time: Moment | None = None
    venue: str | None = Field(default=None, max_length=200)
    resource_id: str | None = Field(default=None, max_length=36)


class ReasonIn(Strict):
    reason: str | None = Field(default=None, max_length=500)


class RoleIn(Strict):
    user_id: str = Field(min_length=1, max_length=36)
    role_name: RoleName
    kind: RoleKind = "cast"
    notes: str | None = Field(default=None, max_length=500)


class RespondIn(Strict):
    decision: Literal["accept", "decline"]
    reason: str | None = Field(default=None, max_length=500)


class TaskIn(Strict):
    title: Title
    due_at: Moment | None = None
    assignee_user_id: str | None = Field(default=None, max_length=36)


def dump(model: BaseModel | None, *, partial: bool = False) -> dict:
    """Plain dict for the service. A partial body keeps only the fields the caller actually sent, so
    PATCH {"venue": null} clears the venue while a body without `venue` leaves it alone."""
    if model is None:
        return {}
    data = model.model_dump(exclude_unset=partial)
    if not partial:
        data = {k: v for k, v in data.items() if v is not None}
    return data
