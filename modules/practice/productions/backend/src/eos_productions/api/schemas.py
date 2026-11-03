"""Request bodies, mirroring contracts/openapi.yaml components."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from ..application.service import NOT_NULLABLE

Kind = Literal["performance", "exhibition", "recital", "screening", "hackathon", "competition", "conference", "other"]
RoleKind = Literal["cast", "crew", "mentor"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ProductionIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    kind: Kind
    department: str | None = Field(default=None, max_length=120)
    summary: str | None = Field(default=None, max_length=2000)
    venue: str | None = Field(default=None, max_length=200)
    resource_id: str | None = Field(default=None, max_length=36)
    lead_user_id: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    call_time: datetime | None = None
    client_token: str | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def dates_come_in_pairs(self):
        if (self.starts_at is None) != (self.ends_at is None):
            raise ValueError("give both starts_at and ends_at, or neither")
        return self


class ProductionPatch(Strict):
    title: str | None = Field(default=None, min_length=1, max_length=200)
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
    starts_at: datetime
    ends_at: datetime
    call_time: datetime | None = None
    venue: str | None = Field(default=None, max_length=200)
    resource_id: str | None = Field(default=None, max_length=36)


class ReasonIn(Strict):
    reason: str | None = Field(default=None, max_length=500)


class RoleIn(Strict):
    user_id: str = Field(min_length=1, max_length=36)
    role_name: str = Field(min_length=1, max_length=120)
    kind: RoleKind = "cast"
    notes: str | None = Field(default=None, max_length=500)


class RespondIn(Strict):
    decision: Literal["accept", "decline"]
    reason: str | None = Field(default=None, max_length=500)


class TaskIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    due_at: datetime | None = None
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
