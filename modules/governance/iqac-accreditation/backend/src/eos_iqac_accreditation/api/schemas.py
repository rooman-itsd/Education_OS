"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field
is a 422, never silently ignored. Every string has an upper bound that fits its column, every date the module's date
range and every number a finite bound, so a value too big is a 422, never a database error."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from ..domain.accreditation import MAX_DATE, MIN_DATE
from ..infrastructure.models import (
    CODE_LEN,
    CRITERION_LEN,
    METRIC_TITLE_LEN,
    NAME_LEN,
    REFERENCE_PART_LEN,
    SOURCE_LEN,
    UNIT_LEN,
    URL_LEN,
)

# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Uuid = Annotated[str, Field(pattern=UUID_PATTERN)]
# format: uri. Only absolute http and https links are kept: they are shown as links to people, and another scheme
# (javascript:, data:) would run in their browser.
Url = Annotated[str, Field(max_length=URL_LEN, pattern=r"^[hH][tT][tT][pP][sS]?://[^\s/?#]+[^\s]*$")]
# Upper bounds of Text columns the contract leaves open, so one request cannot store megabytes.
MAX_DESCRIPTION = 10_000  # framework description, metric guidance, action item description
MAX_NARRATIVE = 20_000
MAX_NOTE = 5_000  # evidence note, action item status note, review comment
MAX_ASSIGNMENTS = 200
# A metric value is a finite number this size at most, so it is exact in the database's double and in JSON.
MAX_VALUE = 1e15


def _in_range(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise ValueError(f"date must be between {MIN_DATE} and {MAX_DATE}")
    return value


Day = Annotated[date, AfterValidator(_in_range)]
Value = Annotated[float, Field(ge=-MAX_VALUE, le=MAX_VALUE, allow_inf_nan=False)]


def text(max_length: int, **kwargs):
    """A string field that is not blank (at least one character other than a space)."""
    return Field(min_length=1, max_length=max_length, pattern=r"\S", **kwargs)


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


def as_dict(body: BaseModel, *, partial: bool, nullable: frozenset[str] = frozenset()) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH, PUT): only the fields the caller
    sent, so only those change; a null is kept only for the `nullable` fields (a value or narrative cleared), so it
    never clears a required one."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None or k in nullable}
    return data


class FrameworkInput(Strict):
    code: str = text(CODE_LEN)
    name: str = text(NAME_LEN)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    active: bool = True


class FrameworkUpdateInput(Strict):
    code: str | None = text(CODE_LEN, default=None)
    name: str | None = text(NAME_LEN, default=None)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    active: bool | None = None


MetricKind = Literal["quantitative", "qualitative"]


class MetricInput(Strict):
    code: str = text(CODE_LEN)
    title: str = text(METRIC_TITLE_LEN)
    criterion: str | None = Field(default=None, max_length=CRITERION_LEN)
    kind: MetricKind
    unit: str | None = Field(default=None, max_length=UNIT_LEN)
    guidance: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    active: bool = True


class MetricUpdateInput(Strict):
    title: str | None = text(METRIC_TITLE_LEN, default=None)
    criterion: str | None = Field(default=None, max_length=CRITERION_LEN)
    unit: str | None = Field(default=None, max_length=UNIT_LEN)
    guidance: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    active: bool | None = None


class CycleInput(Strict):
    framework_id: Uuid
    name: str = text(NAME_LEN)
    period_start: Day
    period_end: Day


class CycleUpdateInput(Strict):
    name: str | None = text(NAME_LEN, default=None)
    period_start: Day | None = None
    period_end: Day | None = None


class CycleStatusInput(Strict):
    status: Literal["collecting", "under_review", "submitted", "closed"]
    submitted_on: Day | None = None


class Assignment(Strict):
    metric_id: Uuid
    owner_id: Uuid
    due_on: Day


class AssignmentInput(Strict):
    assignments: list[Assignment] = Field(min_length=1, max_length=MAX_ASSIGNMENTS)


class ResponseInput(Strict):
    value: Value | None = None
    narrative: str | None = Field(default=None, max_length=MAX_NARRATIVE)


class Reference(Strict):
    module: str = text(REFERENCE_PART_LEN)
    entity: str = text(REFERENCE_PART_LEN)
    id: str = text(REFERENCE_PART_LEN)


class EvidenceInput(Strict):
    title: str = text(NAME_LEN)
    kind: Literal["link", "reference"]
    url: Url | None = None
    reference: Reference | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE)


class ReviewInput(Strict):
    decision: Literal["accept", "return"]
    comment: str | None = Field(default=None, min_length=3, max_length=MAX_NOTE)


class ActionItemInput(Strict):
    title: str = text(NAME_LEN)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    source: str | None = Field(default=None, max_length=SOURCE_LEN)
    cycle_id: Uuid | None = None
    metric_id: Uuid | None = None
    owner_id: Uuid
    due_on: Day


class ActionItemUpdateInput(Strict):
    title: str | None = text(NAME_LEN, default=None)
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    source: str | None = Field(default=None, max_length=SOURCE_LEN)
    owner_id: Uuid | None = None
    due_on: Day | None = None
    status: Literal["in_progress", "done", "cancelled"] | None = None
    note: str | None = Field(default=None, max_length=MAX_NOTE)
