"""Input of the meetings port (contracts/ports/meetings.yaml), validated before anything is sent to a provider. Every
string, number, list and date is bounded; NaN and Infinity are refused; a failure names the field, never the value."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Annotated, Any, Literal
from uuid import UUID
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, ValidationError, field_validator

from .errors import AdapterError

NoControl = r"^[^\x00-\x1f\x7f]*$"
Key = Annotated[str, StringConstraints(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9._:@/\-]+$")]
Title = Annotated[str, StringConstraints(min_length=1, max_length=300, pattern=NoControl)]
Name = Annotated[str, StringConstraints(min_length=1, max_length=200, pattern=NoControl)]
Email = Annotated[
    str,
    StringConstraints(
        min_length=3, max_length=254, pattern=r"^[^@\s,;<>\"]{1,64}@[A-Za-z0-9.\-]{1,190}\.[A-Za-z]{2,24}$"
    ),
]
ProviderUser = Annotated[str, StringConstraints(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9._@+\-]+$")]
Domain = Annotated[str, StringConstraints(min_length=3, max_length=190, pattern=r"^[A-Za-z0-9.\-]+\.[A-Za-z]{2,24}$")]
Role = Literal["host", "co_host", "attendee"]
MIN_DATE, MAX_DATE = datetime(2000, 1, 1, tzinfo=UTC), datetime(2100, 1, 1, tzinfo=UTC)


class _In(BaseModel):
    model_config = ConfigDict(extra="ignore", allow_inf_nan=False, str_strip_whitespace=True)


def _aware(v: Any) -> datetime:
    if not isinstance(v, datetime):
        raise ValueError("not a date-time")
    if v.tzinfo is None:
        raise ValueError("needs a time zone offset")
    if not MIN_DATE <= v <= MAX_DATE:
        raise ValueError("out of range")
    return v.astimezone(UTC)


class Host(_In):
    person_id: UUID | None = None
    email: Email | None = None
    provider_user_id: ProviderUser | None = None

    @field_validator("provider_user_id", mode="before")
    @classmethod
    def _blank(cls, v):
        return v or None


class CoHost(_In):
    person_id: UUID | None = None
    email: Email


class Options(_In):
    waiting_room: bool = True
    record: Literal["none", "cloud", "local"] = "none"
    join_before_host: bool = False
    authenticated_join_only: bool = False
    auto_admit_domain: Domain | None = None

    @field_validator("auto_admit_domain", mode="before")
    @classmethod
    def _blank(cls, v):
        return v or None


class CreateMeeting(_In):
    meeting_key: Key
    meeting_id: UUID | None = None  # the hub's id for the meeting, when it has chosen one
    caller_module: Annotated[str, StringConstraints(max_length=60, pattern=r"^[a-z0-9\-]*$")] | None = None
    title: Title
    starts_at: datetime
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=1440)]
    timezone: Annotated[str, StringConstraints(min_length=1, max_length=64)] = "UTC"
    host: Host
    co_hosts: list[CoHost] = Field(default_factory=list, max_length=50)
    options: Options = Field(default_factory=Options)

    @field_validator("starts_at")
    @classmethod
    def _starts(cls, v):
        return _aware(v)

    @field_validator("timezone")
    @classmethod
    def _tz(cls, v):
        if not re.fullmatch(r"[A-Za-z0-9_+\-/]{1,64}", v):
            raise ValueError("not an IANA zone")
        try:
            ZoneInfo(v)
        except (KeyError, ValueError, OSError) as e:
            raise ValueError("not an IANA zone") from e
        return v


class UpdateMeeting(_In):
    meeting_key: Key
    title: Title | None = None
    starts_at: datetime | None = None
    duration_minutes: Annotated[int, Field(strict=True, ge=1, le=1440)] | None = None
    host: Host | None = None
    options: Options | None = None

    @field_validator("starts_at")
    @classmethod
    def _starts(cls, v):
        return None if v is None else _aware(v)


class CancelMeeting(_In):
    meeting_key: Key
    reason: Annotated[str, StringConstraints(max_length=500, pattern=NoControl)] | None = None


class MeetingRef(_In):
    meeting_key: Key


class RosterEntry(_In):
    person_id: UUID
    email: Email


class FetchAttendance(_In):
    meeting_key: Key
    # The adapter has no directory of people: the caller names who may be matched by email (docs: contract deviations).
    roster: list[RosterEntry] = Field(default_factory=list, max_length=5000)


class JoinLink(_In):
    meeting_key: Key
    person_id: UUID
    display_name: Name
    email: Email | None = None
    role: Role = "attendee"


class ImportRecording(_In):
    meeting_key: Key
    provider_recording_id: Annotated[
        str, StringConstraints(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_=+\-][A-Za-z0-9._=+\-]*$")
    ]


def parse[T: _In](model: type[T], data: Any) -> T:
    """Validate an operation's input, or fail as invalid_request naming the fields and never echoing a value."""
    if not isinstance(data, dict):
        raise AdapterError("invalid_request", "the input must be an object")
    try:
        return model.model_validate(data)
    except ValidationError as e:
        fields = sorted({".".join(str(p) for p in err["loc"]) or "input" for err in e.errors()})
        raise AdapterError("invalid_request", "invalid input: " + ", ".join(fields)[:300]) from None
