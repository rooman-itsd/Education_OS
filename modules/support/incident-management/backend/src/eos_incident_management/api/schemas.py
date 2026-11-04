"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field
is a 422, never silently ignored.

Upper bounds the contract leaves open are set here to what the columns hold, so a value too long or a list too big
is a 422, never a database error. Date-times are kept within MIN_YEAR and MAX_YEAR in UTC, so converting an offset
at the calendar ends (0001-01-01T00:00+05:00, 9999-12-31T23:59-05:00) is a 422 instead of an overflow."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

MIN_YEAR, MAX_YEAR = 2000, 2100
MAX_TEXT = 20_000  # descriptions, timeline updates, summaries and other Text columns
MAX_LABELS = 20  # affected services per incident or problem
MAX_PEOPLE = 50  # responders per incident
MAX_ITEMS = 50  # contributing factors and attachments per RCA


def _moment(value: datetime) -> datetime:
    """Any date-time as UTC. One without an offset is taken as UTC (decision: the contract's date-time is RFC 3339,
    which always has one, so a naive value is read the way the module stores everything)."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=UTC)
    try:
        value = value.astimezone(UTC)
    except OverflowError:
        raise ValueError(f"date-time must be between {MIN_YEAR} and {MAX_YEAR}") from None
    if not MIN_YEAR <= value.year <= MAX_YEAR:
        raise ValueError(f"date-time must be between {MIN_YEAR} and {MAX_YEAR}")
    return value


def _day(value: date) -> date:
    if not MIN_YEAR <= value.year <= MAX_YEAR:
        raise ValueError(f"date must be between {MIN_YEAR} and {MAX_YEAR}")
    return value


# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
Moment = Annotated[datetime, AfterValidator(_moment)]
Day = Annotated[date, AfterValidator(_day)]
Severity = Literal["critical", "high", "medium", "low"]
Relation = Literal["related_ticket", "affected_asset", "work_order"]
Label = Annotated[str, Field(min_length=1, max_length=80)]  # contract ServiceLabels items: maxLength 80
Labels = Annotated[list[Label], Field(max_length=MAX_LABELS)]
People = Annotated[list[Uuid], Field(max_length=MAX_PEOPLE)]
Title = Annotated[str, Field(min_length=3, max_length=200)]  # String(200)
Text = Annotated[str, Field(max_length=MAX_TEXT)]
LongText = Annotated[str, Field(min_length=3, max_length=MAX_TEXT)]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Fields the contract lets a PATCH set to null (`oneOf: [..., {type: "null"}]` or `type: [..., "null"]`).
NULLABLE_ON_PATCH = frozenset({"problem_id", "reference"})


def as_dict(body: BaseModel, *, partial: bool) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH): only the fields the caller
    sent, so only those change; a null is kept only where the contract allows one, so it never clears a required
    value."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None or k in NULLABLE_ON_PATCH}
    return data


class ReferenceInput(Strict):
    module: str = Field(min_length=1, max_length=60)
    entity: str = Field(min_length=1, max_length=60)
    id: str = Field(min_length=1, max_length=100)
    relation: Relation
    note: Text | None = None


class IncidentInput(Strict):
    title: Title
    description: LongText
    affected_services: Labels | None = None
    severity: Severity
    started_at: Moment | None = None
    lead_id: Uuid | None = None
    responder_ids: People | None = None


class IncidentUpdateInput(Strict):
    title: Title | None = None
    description: Text | None = None
    affected_services: Labels | None = None
    severity: Severity | None = None
    started_at: Moment | None = None
    lead_id: Uuid | None = None
    responder_ids: People | None = None
    problem_id: Uuid | None = None


class IncidentStatusInput(Strict):
    status: Literal["investigating", "mitigated", "resolved", "closed", "cancelled"]
    resolution_summary: LongText | None = None
    note: LongText | None = None


class TimelineInput(Strict):
    body: Annotated[str, Field(min_length=1, max_length=MAX_TEXT)]


class ProblemInput(Strict):
    title: Title
    description: LongText
    affected_services: Labels | None = None
    owner_id: Uuid | None = None


class ProblemUpdateInput(Strict):
    title: Title | None = None
    description: Text | None = None
    affected_services: Labels | None = None
    owner_id: Uuid | None = None
    workaround: Text | None = None


class ProblemStatusInput(Strict):
    status: Literal["investigating", "known_error", "resolved", "closed"]
    workaround: LongText | None = None


class RcaInput(Strict):
    summary: LongText
    root_cause: LongText
    contributing_factors: (
        Annotated[list[Annotated[str, Field(max_length=2000)]], Field(max_length=MAX_ITEMS)] | None
    ) = None
    attachment_document_ids: (
        Annotated[list[Annotated[str, Field(min_length=1, max_length=100)]], Field(max_length=MAX_ITEMS)] | None
    ) = None


class ActionInput(Strict):
    description: LongText
    owner_id: Uuid
    due_date: Day
    reference: ReferenceInput | None = None


class ActionUpdateInput(Strict):
    description: LongText | None = None
    owner_id: Uuid | None = None
    due_date: Day | None = None
    reference: ReferenceInput | None = None
    status: Literal["done", "cancelled"] | None = None
