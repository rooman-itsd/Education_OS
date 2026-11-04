"""Request bodies, mirroring contracts/openapi.yaml components.schemas. Extra fields are refused, so a misspelt field
is a 422, never silently ignored. Upper bounds the contract leaves open are set to what the columns hold (or, for
Text and JSON columns, to sizes no real article needs), so a value too big is a 422, never a database error."""

from __future__ import annotations

from datetime import date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

# The contract types ids as format: uuid. Checked here so a bad id is a 422, never a stored row.
Uuid = Annotated[str, Field(pattern=r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")]
ArticleType = Literal["article", "faq", "how_to"]
Audience = Literal["everyone", "staff"]
Tag = Annotated[str, Field(max_length=40)]
Slug = Annotated[str, Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=120)]
# Dates a person would type: a review date, a publication date. Keeps date arithmetic and comparisons well inside the
# calendar.
Day = Annotated[date, Field(ge=date(1900, 1, 1), le=date(9000, 12, 31))]

MAX_POSITION = 100_000
MAX_BODY = 200_000  # characters of Markdown
MAX_TEXT = 5_000
MAX_ITEMS = 50


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*")
    @classmethod
    def _no_nul(cls, value):
        """Postgres text cannot hold NUL characters; refused here (422) rather than failing in the database (500)."""
        values = value if isinstance(value, list) else [value]
        if any(isinstance(v, str) and "\x00" in v for v in values):
            raise ValueError("text must not contain NUL characters")
        return value


# Fields the contract lets a PATCH set to null (`type: [..., "null"]`).
NULLABLE_ON_PATCH = frozenset({"parent_id", "review_by"})


def as_dict(body: BaseModel, *, partial: bool) -> dict:
    """Request values for the use cases, nested models as plain dicts. partial (PATCH): only the fields the caller
    sent, so only those change; a null is kept only where the contract allows one, so it never clears a required
    value."""
    data = body.model_dump(exclude_unset=partial)
    if partial:
        data = {k: v for k, v in data.items() if v is not None or k in NULLABLE_ON_PATCH}
    return data


class CategoryInput(Strict):
    parent_id: Uuid | None = None
    name: str = Field(min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=MAX_TEXT)
    position: int | None = Field(default=None, ge=0, le=MAX_POSITION)
    active: bool = True


class CategoryUpdateInput(Strict):
    """PATCH /categories/{id}: CategoryInput with every field optional; only the fields sent change."""

    parent_id: Uuid | None = None
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=MAX_TEXT)
    position: int | None = Field(default=None, ge=0, le=MAX_POSITION)
    active: bool | None = None


class ReferenceInput(Strict):
    module: str = Field(min_length=1, max_length=60)
    entity: str = Field(min_length=1, max_length=60)
    id: str = Field(min_length=1, max_length=100)
    note: str | None = Field(default=None, max_length=500)


class RevisionFields(Strict):
    type: ArticleType | None = None
    title: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=500)
    body: str | None = Field(default=None, min_length=1, max_length=MAX_BODY)
    category_id: Uuid | None = None
    tags: list[Tag] | None = Field(default=None, max_length=MAX_ITEMS)
    audience: Audience | None = None
    related_article_ids: list[Uuid] | None = Field(default=None, max_length=MAX_ITEMS)
    references: list[ReferenceInput] | None = Field(default=None, max_length=MAX_ITEMS)


class DraftInput(RevisionFields):
    change_note: str | None = Field(default=None, max_length=500)


class ArticleCreateInput(RevisionFields):
    type: ArticleType
    title: str = Field(min_length=3, max_length=200)
    body: str = Field(min_length=1, max_length=MAX_BODY)
    category_id: Uuid
    audience: Audience
    change_note: str | None = Field(default=None, max_length=500)
    slug: Slug | None = None
    owner_id: Uuid | None = None
    review_by: Day | None = None


class ArticleSettingsInput(Strict):
    owner_id: Uuid | None = None
    review_by: Day | None = None


class ReturnInput(Strict):
    comment: str = Field(min_length=3, max_length=MAX_TEXT)


class PublishInput(Strict):
    review_by: Day | None = None


class Reason(Strict):
    reason: str = Field(min_length=3, max_length=MAX_TEXT)


class FeedbackInput(Strict):
    helpful: bool
    comment: str | None = Field(default=None, max_length=1000)
