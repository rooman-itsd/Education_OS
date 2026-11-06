"""Input of the wearable-data port (contracts/ports/wearable-data.yaml), validated before anything is sent to a provider
or read from the database. Every string, number, list and date is bounded; NaN and Infinity are refused; a failure names
the field, never the value."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator, model_validator

from .errors import AdapterError

DATA_TYPES = ("daily_summary", "activity", "sleep", "heart_rate_variability", "body_composition")
DataType = Literal["daily_summary", "activity", "sleep", "heart_rate_variability", "body_composition"]
MIN_DATE, MAX_DATE = date(2000, 1, 1), date(2100, 1, 1)
MAX_SPAN_DAYS = 731
NoControl = r"^[^\x00-\x1f\x7f]*$"
Token = Annotated[str, StringConstraints(min_length=1, max_length=512, pattern=NoControl)]
Purpose = Annotated[str, StringConstraints(min_length=3, max_length=40, pattern=r"^[a-z][a-z0-9_]*$")]
Module = Annotated[str, StringConstraints(max_length=60, pattern=r"^[a-z0-9\-]*$")]


class _In(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False, str_strip_whitespace=True)


def _day(v: Any) -> date:
    if not isinstance(v, date):
        raise ValueError("not a date")
    if not MIN_DATE <= v <= MAX_DATE:
        raise ValueError("out of range")
    return v


class _Range(_In):
    @model_validator(mode="after")
    def _range(self):
        lo, hi = getattr(self, "from_", None), getattr(self, "to", None)
        if lo is not None and hi is not None:
            if hi < lo:
                raise ValueError("to is before from")
            if (hi - lo).days > MAX_SPAN_DAYS:
                raise ValueError("range too long")
        return self


class LinkAccount(_In):
    person_id: UUID
    provider: Annotated[str, StringConstraints(min_length=1, max_length=20)]
    data_types: list[DataType] = Field(default_factory=list, max_length=5)
    return_url: Annotated[str, StringConstraints(max_length=2000, pattern=r"^https?://[^\s]+$")] | None = None
    account_link_id: UUID | None = None  # the hub's id for the link, when it has made one
    # What begin_authorisation needs; the hub owns state and the PKCE verifier.
    state: Token
    code_challenge: Annotated[str, StringConstraints(min_length=43, max_length=128, pattern=r"^[A-Za-z0-9\-._~]+$")]
    redirect_uri: Annotated[str, StringConstraints(max_length=2000, pattern=r"^https?://[^\s]+$")]
    # DPDP Act: a minor's device cannot be linked until a guardian's consent is recorded elsewhere.
    minor: bool = False
    guardian_consent_recorded: bool = False


class UnlinkAccount(_In):
    account_link_id: UUID
    reason: Annotated[str, StringConstraints(max_length=200, pattern=NoControl)] | None = None


class Sync(_Range):
    account_link_id: UUID
    data_types: list[DataType] = Field(default_factory=list, max_length=5)
    from_: date | None = Field(default=None, alias="from")
    to: date | None = None

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False, populate_by_name=True)

    @field_validator("from_", "to")
    @classmethod
    def _bounded(cls, v):
        return None if v is None else _day(v)


class Read(_Range):
    person_id: UUID
    data_type: DataType
    from_: date = Field(alias="from")
    to: date
    purpose: Purpose
    caller_module: Module | None = None
    requester_person_id: UUID | None = None  # who is asking, when the purpose is the athlete's own view
    cursor: Annotated[str, StringConstraints(max_length=200)] | None = None
    limit: Annotated[int, Field(strict=True, ge=1, le=500)] = 100

    model_config = ConfigDict(extra="ignore", allow_inf_nan=False, populate_by_name=True)

    @field_validator("from_", "to")
    @classmethod
    def _bounded(cls, v):
        return _day(v)


class LinkStatus(_In):
    person_ids: list[UUID] = Field(max_length=200)


def parse[T: _In](model: type[T], data: Any) -> T:
    """Validate an operation's input, or fail as invalid_request naming the fields and never echoing a value."""
    if not isinstance(data, dict):
        raise AdapterError("invalid_request", "the input must be an object")
    try:
        return model.model_validate(data)
    except ValidationError as e:
        fields = sorted({".".join(str(p) for p in err["loc"]) or "input" for err in e.errors()})
        raise AdapterError("invalid_request", "invalid input: " + ", ".join(fields)[:300]) from None
