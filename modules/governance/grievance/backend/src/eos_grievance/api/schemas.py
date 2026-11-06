"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field is a
422, never silently ignored. Every string has an upper bound that fits its column, every date the module's date range, so
a value too big is a 422, never a database error."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from ..domain.cases import (
    APPEAL_OUTCOMES,
    COMMITTEE_KINDS,
    DECISION_OUTCOMES,
    MAX_DATE,
    MEMBER_ROLES,
    MIN_DATE,
    PROCEEDING_KINDS,
    TRACKS,
)
from ..infrastructure.models import CATEGORY_LEN, MAX_MEMBERS, NAME_LEN, REASON_LEN, RESPONDENT_LEN, TEXT_LEN

# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Uuid = Annotated[str, Field(pattern=UUID_PATTERN)]
Track = Literal[TRACKS]  # type: ignore[valid-type]
CommitteeKind = Literal[COMMITTEE_KINDS]  # type: ignore[valid-type]
MemberRole = Literal[MEMBER_ROLES]  # type: ignore[valid-type]


def _in_range(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise ValueError(f"date must be between {MIN_DATE} and {MAX_DATE}")
    return value


Day = Annotated[date, AfterValidator(_in_range)]


def text(max_length: int, min_length: int = 1, **kwargs):
    """A string field with at least `min_length` characters, not blank (at least one character other than a space)."""
    return Field(min_length=min_length, max_length=max_length, pattern=r"\S", **kwargs)


def _has_nul(value) -> bool:
    if isinstance(value, str):
        return "\x00" in value
    if isinstance(value, (list, tuple)):
        return any(_has_nul(v) for v in value)
    if isinstance(value, dict):
        return any(_has_nul(k) or _has_nul(v) for k, v in value.items())
    if isinstance(value, BaseModel):
        return _has_nul(value.model_dump())
    return False


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*")
    @classmethod
    def _no_nul(cls, value):
        """Postgres text cannot hold NUL characters; refused here (422) rather than failing in the database (500)."""
        if _has_nul(value):
            raise ValueError("text must not contain NUL characters")
        return value


def as_dict(body: BaseModel, *, partial: bool) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH): only the fields the caller sent,
    so only those change; a null never clears a required value."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None}
    return data


class Member(Strict):
    person_id: Uuid
    role: MemberRole


class CommitteeInput(Strict):
    name: str = text(NAME_LEN)
    kind: CommitteeKind
    members: list[Member] = Field(default_factory=list, max_length=MAX_MEMBERS)
    active: bool = True


class CommitteeUpdateInput(Strict):
    name: str | None = text(NAME_LEN, default=None)
    members: list[Member] | None = Field(default=None, max_length=MAX_MEMBERS)
    active: bool | None = None


class Respondent(Strict):
    person_id: Uuid | None = None
    description: str | None = text(RESPONDENT_LEN, default=None)


class GrievanceInput(Strict):
    track: Track
    committee_id: Uuid | None = None
    category: str = text(CATEGORY_LEN)
    description: str = text(TEXT_LEN, min_length=10)
    incident_date: Day | None = None
    respondent: Respondent | None = None


class UpdateInput(Strict):
    body: str = text(TEXT_LEN)


class WithdrawInput(Strict):
    reason: str | None = text(REASON_LEN, default=None)


class AppealInput(Strict):
    reason: str = text(TEXT_LEN, min_length=10)


class StatusInput(Strict):
    status: Literal["acknowledged", "under_inquiry", "not_admitted", "closed"]
    reason: str | None = text(REASON_LEN, min_length=3, default=None)


class ProceedingInput(Strict):
    kind: Literal[PROCEEDING_KINDS]  # type: ignore[valid-type]
    held_on: Day
    summary: str = text(TEXT_LEN, min_length=3)


class DecisionInput(Strict):
    outcome: Literal[DECISION_OUTCOMES]  # type: ignore[valid-type]
    findings: str = text(TEXT_LEN, min_length=3)
    actions_recommended: str | None = text(TEXT_LEN, default=None)


class TransferInput(Strict):
    committee_id: Uuid
    reason: str = text(REASON_LEN, min_length=3)


class AppealDecisionInput(Strict):
    outcome: Literal[APPEAL_OUTCOMES]  # type: ignore[valid-type]
    outcome_note: str = text(TEXT_LEN, min_length=3)
