"""Request bodies, mirroring contracts/openapi.yaml components. Optional fields left out of a PATCH body keep
their stored value, so handlers dump with exclude_unset. Every string and list is bounded (the contract's maxLength
where it gives one, a column-sized bound otherwise) so nothing oversized reaches the database."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
# The contract types every id as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=UUID_PATTERN)]
# Scores and weights are percentages; NaN and infinity are refused too.
Percent = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]
Note = Annotated[str, Field(min_length=1, max_length=4000)]
Comments = Annotated[str, Field(max_length=4000)]


def _in_range(value: date) -> date:
    """Dates near year 1 or 9999 overflow in date arithmetic (days left, the overdue window); no project is that far."""
    if not 1900 <= value.year <= 9998:
        raise ValueError("must be between the years 1900 and 9998")
    return value


Day = Annotated[date, AfterValidator(_in_range)]

MAX_TEAM = 50
MAX_GUIDES = 20
MAX_DOCUMENTS = 20


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


class ProjectFieldsIn(Strict):
    """ProjectFields. In a PATCH every field is optional; external_partner may be cleared with null."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    kind: str | None = Field(default=None, max_length=100)
    academic_year: str | None = Field(default=None, max_length=20)
    starts_on: Day | None = None
    ends_on: Day | None = None
    external_partner: str | None = Field(default=None, max_length=200)


class ProjectCreateIn(ProjectFieldsIn):
    title: str = Field(min_length=1, max_length=200)
    starts_on: Day
    ends_on: Day
    member_ids: list[Uuid] = Field(default_factory=list, max_length=MAX_TEAM)
    lead_id: Uuid | None = None
    guide_ids: list[Uuid] = Field(default_factory=list, max_length=MAX_GUIDES)


class DecisionIn(Strict):
    decision: Literal["approved", "rejected"]
    guide_ids: list[Uuid] = Field(default_factory=list, max_length=MAX_GUIDES)
    reason: str | None = Field(default=None, max_length=2000)


class MemberIn(Strict):
    person_id: Uuid
    role: Literal["lead", "member"] = "member"


class GuidesIn(Strict):
    guide_ids: list[Uuid] = Field(min_length=1, max_length=MAX_GUIDES)


class ReasonIn(Strict):
    reason: str = Field(min_length=3, max_length=2000)


class MilestoneIn(Strict):
    title: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    due_on: Day
    weight: Percent | None = None


class MilestoneUpdateIn(Strict):
    """MilestoneUpdate. Every field is optional so a milestone can be moved or cancelled without resending it."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=4000)
    due_on: Day | None = None
    weight: Percent | None = None
    status: Literal["cancelled"] | None = None
    reason: str | None = Field(default=None, max_length=2000)


class SubmissionIn(Strict):
    note: Note
    document_ids: list[Uuid] = Field(default_factory=list, max_length=MAX_DOCUMENTS)


class ReviewIn(Strict):
    decision: Literal["accepted", "returned"]
    comments: Comments | None = None
    score: Percent | None = None


class EvaluationIn(Strict):
    decision: Literal["completed", "returned"]
    outcome: str | None = Field(default=None, max_length=100)
    score: Percent | None = None
    comments: Comments | None = None
