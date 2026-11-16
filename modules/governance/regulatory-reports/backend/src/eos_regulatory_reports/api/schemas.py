"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field
is a 422, never silently ignored. Every string has an upper bound that fits its column, every date the module's date
range, so a value too big is a 422, never a database error."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, field_validator

from ..domain.filings import MAX_DATE, MIN_DATE
from ..infrastructure.models import AUTHORITY_LEN, PERIOD_LABEL_LEN, REFERENCE_LEN, TITLE_LEN, URL_LEN

# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
UUID_PATTERN = r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
Uuid = Annotated[str, Field(pattern=UUID_PATTERN)]
# format: uri. Only absolute http and https links are kept: they are shown as links to people, and another scheme
# (javascript:, data:) would run in their browser.
Url = Annotated[str, Field(max_length=URL_LEN, pattern=r"^[hH][tT][tT][pP][sS]?://[^\s/?#]+[^\s]*$")]
Recurrence = Literal["once", "monthly", "quarterly", "half_yearly", "annual"]
# Upper bounds of Text columns the contract leaves open, so one request cannot store megabytes.
MAX_DESCRIPTION = 10_000
MAX_NOTES = 20_000
MAX_NOTE = 2_000  # a return comment or a not-applicable reason
MAX_LINKS = 50


def _in_range(value: date) -> date:
    if not MIN_DATE <= value <= MAX_DATE:
        raise ValueError(f"date must be between {MIN_DATE} and {MAX_DATE}")
    return value


Day = Annotated[date, AfterValidator(_in_range)]


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


# Fields the contract lets a PATCH set to null (`type: [..., "null"]`).
NULLABLE_ON_PATCH = frozenset({"portal_url", "default_owner_id"})


def as_dict(body: BaseModel, *, partial: bool) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH): only the fields the caller
    sent, so only those change; a null is kept only where the contract allows one, so it never clears a required
    value."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None or k in NULLABLE_ON_PATCH}
    return data


class Link(Strict):
    title: str = text(TITLE_LEN)
    url: Url


class ObligationInput(Strict):
    title: str = text(TITLE_LEN)
    authority: str = text(AUTHORITY_LEN)
    portal_url: Url | None = None
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    recurrence: Recurrence
    default_owner_id: Uuid | None = None
    active: bool = True


class ObligationUpdateInput(Strict):
    title: str | None = text(TITLE_LEN, default=None)
    authority: str | None = text(AUTHORITY_LEN, default=None)
    portal_url: Url | None = None
    description: str | None = Field(default=None, max_length=MAX_DESCRIPTION)
    recurrence: Recurrence | None = None
    default_owner_id: Uuid | None = None
    active: bool | None = None


class FilingInput(Strict):
    period_label: str = text(PERIOD_LABEL_LEN)
    period_start: Day
    period_end: Day
    due_on: Day
    owner_id: Uuid | None = None


class FilingUpdateInput(Strict):
    preparation_notes: str | None = Field(default=None, max_length=MAX_NOTES)
    links: list[Link] | None = Field(default=None, max_length=MAX_LINKS)
    owner_id: Uuid | None = None
    due_on: Day | None = None
    period_label: str | None = text(PERIOD_LABEL_LEN, default=None)
    period_start: Day | None = None
    period_end: Day | None = None


class FilingStatusInput(Strict):
    status: Literal["in_preparation", "under_review", "not_applicable"]
    comment: str | None = Field(default=None, min_length=3, max_length=MAX_NOTE)
    reason: str | None = Field(default=None, min_length=3, max_length=MAX_NOTE)


class SubmitInput(Strict):
    submitted_on: Day
    submission_reference: str = text(REFERENCE_LEN)


class AcknowledgeInput(Strict):
    acknowledged_on: Day
    acknowledgement_reference: str | None = Field(default=None, max_length=REFERENCE_LEN)
